import base64
import logging
import os
import uuid
from collections import UserDict
from zope.interface import implementer

from pyramid.compat import (
    bytes_,
    native_,
    text_,
)
from pyramid.interfaces import ISession
from sqlalchemy import inspect

from .config import (
    get_config_defaults,
    _process_factory_args,
)
from .config.settings import (
    SessionSettings,
    _BaseSettings,
    _ConfigAbsoluteSettings,
    _ConfigCookieSettings,
    _ConfigIdleSettings,
    _ConfigRenewalSettings,
)
from .events import (
    InvalidCookieErrorEvent,
    CookieCryptoErrorEvent,
    RenewalViolationEvent,
)
from .exceptions import (
    InvalidCookieError,
    CookieCryptoError,
    InconsistentDataError,
)
from .model import CSRF_TOKEN_SIZE
from .util import (
    weighted_truth,
    int_now,
)


def initializes_session(meth):
    """ Decorator which initializes the session when decorated method is
    called. """
    def wrapper(session, *arg, **kw):
        if session._session is None:
            session._init_request_session()
        return meth(session, *arg, **kw)
    wrapper.__doc__ = meth.__doc__
    return wrapper


def notifies_changed_data(meth):
    """ Decorator which initializes the session and calls changed() method,
    notifying the session that the main data dict may have dirty data,
    including deeply nested changes. """
    def wrapper(session, *arg, **kw):
        if session._session is None:
            session._init_request_session()
        session.changed()
        return meth(session, *arg, **kw)
    wrapper.__doc__ = meth.__doc__
    return wrapper


class SessionProperty:
    """ Simple descriptor that will proxy reads and writes to the attached
    ORM session instance and mark the session dirty on writes. """
    def __init__(self, name):
        self.name = name

    def __get__(self, obj, type=None):
        if obj._session is None:
            obj._init_request_session()
        return getattr(obj._session, self.name)

    def __set__(self, obj, value):
        if obj._session is None:
            obj._init_request_session()
        setattr(obj._session, self.name, value)
        obj._dirty = True


class ReadOnlyProperty(SessionProperty):
    """ Descriptor that will read session attribute and prevent any writes."""
    def __set__(self, obj, value):
        raise NotImplementedError("The attribute is read-only.")


def get_session_factory(serializer, model_class, **kw):
    """
    Return :term:`session factory` constructed using settings provided by 
    the arguments.
    
    Arguments:
    
    serializer
        a :term:`serializer` object (**required**)
    model_class
        session :term:`model` object (**required**)
    
    Other keyword arguments are optional (using library defaults when 
    not provided). See :ref:`settings` for details.
    """
    s = {
        'serializer': serializer,
        'model_class': model_class,
    }
    for name, default in get_config_defaults().items():
        s[name] = kw.get(name, default)

    settings = _process_factory_args(s)
    mixin_features = {
        'enable_userid': _UseridSession,
        'enable_csrf': _CSRFSession,
        'enable_configcookie': _ConfigCookieSession,
    }
    bases = [_BaseSession]
    for name, mixin in mixin_features.items():
        if settings[name]:
            bases.append(mixin)
    mixin_config_features = {
        'config_renewal': (_ConfigRenewalSession, _RenewalSession),
        'config_idle': (_ConfigIdleSession, _IdleSession),
        'config_absolute': (_ConfigAbsoluteSession, _AbsoluteSession),
    }
    for name, mixins in mixin_config_features.items():
        if settings[name] is not None:
            bases.append(mixins[0] if settings[name] else mixins[1])
    bases = tuple(reversed(bases))
    cls = type('FrankenSession', bases, {})
    attrs = {
        '_logger': logging.getLogger(__name__)
    }
    for name, value in settings.items():
        attrs['_' + name] = value
    for name, value in attrs.items():
        setattr(cls, name, value)
    return cls


@implementer(ISession)
class _ISessionSession(UserDict):
    """ Session mixin implementing ISession API """
    created = ReadOnlyProperty('created')

    @property
    @initializes_session
    def new(self):
        return self._new

    @new.setter
    @initializes_session
    def new(self, value):
        raise NotImplementedError('The attribute is read-only.')

    def changed(self):
        """ Mark the session as dirty when the main data dict is changed. """
        self._dirty = True
        if not self.new:
            self._session.data.changed()

    @initializes_session
    def invalidate(self):
        """ Invalidate the current session. """
        self.clear()
        state = inspect(self._session)
        # Deleted and detached states should not be possible.
        log_msg = "Invalidating %s session %s"
        if state.persistent:
            self._logger.info(log_msg % ('persistent', self._session.id))
            self._delete_session(self._session)
        elif state.pending:
            self._logger.info(log_msg % ('pending', self._session.id))
            self._dbsession.expunge(self._session)
        self.settings.discard()
        self._init_session_instance()

    @initializes_session
    def flash(self, msg, queue='', allow_duplicate=True):
        assert isinstance(msg, str)
        assert isinstance(queue, str)
        storage = self._session.flash.setdefault(queue, [])
        if allow_duplicate or (msg not in storage):
            storage.append(msg)
            self._dirty = True

    @initializes_session
    def pop_flash(self, queue=''):
        if len(self._session.flash):
            storage = self._session.flash.pop(queue, [])
            self._dirty = True
            return storage
        else:
            return []

    @initializes_session
    def peek_flash(self, queue=''):
        storage = self._session.flash.get(queue, [])
        return storage

    get = initializes_session(UserDict.get)
    __getitem__ = initializes_session(UserDict.__getitem__)
    items = initializes_session(UserDict.items)
    values = initializes_session(UserDict.values)
    keys = initializes_session(UserDict.keys)
    __contains__ = initializes_session(UserDict.__contains__)
    __len__ = initializes_session(UserDict.__len__)
    __iter__ = initializes_session(UserDict.__iter__)

    clear = notifies_changed_data(UserDict.clear)
    update = notifies_changed_data(UserDict.update)
    setdefault = notifies_changed_data(UserDict.setdefault)
    pop = notifies_changed_data(UserDict.pop)
    popitem = notifies_changed_data(UserDict.popitem)
    __setitem__ = notifies_changed_data(UserDict.__setitem__)
    __delitem__ = notifies_changed_data(UserDict.__delitem__)


class _BaseSession(_ISessionSession):
    """ Provides minimal working session without any extra features. """
    def __init__(self, request):
        self.request = request
        self._new = True
        self._dbsession = getattr(request, self._dbsession_name)
        self._session = None
        self._cookieval = None
        self._cookie_callback_added = False
        self._existing_invalidated = False
        self._cookie_action = None
        self._new_cookie = None
        self._renewal_id = None
        self._settings = None

    def _init_request_session(self):
        """ Try to init session instance based on request data """
        session = None
        cookie_raw = self.request.cookies.get(self._cookie_name)
        if cookie_raw is not None:
            try:
                unpacked = self._serializer.loads(bytes_(cookie_raw))
                id = uuid.UUID(bytes=unpacked[:16])
                session = self._load_session(id)
                if session is not None and self._config_renewal is not None:
                    if self._config_renewal:
                        renewal_timeout = session.renewal_timeout
                    else:
                        renewal_timeout = self._renewal_timeout
                    if renewal_timeout is not None:
                        self._renewal_id = uuid.UUID(bytes=unpacked[16:32])

            except InvalidCookieError as exc:
                self._logger.warning(
                    'Invalid session cookie found (%s).' % cookie_raw
                )
                self._fire_event(InvalidCookieErrorEvent, exc)
            except CookieCryptoError as exc:
                self._logger.warning(
                    'Could not decrypt/authenticate session cookie (%s).'
                    % cookie_raw
                )
                self._fire_event(CookieCryptoErrorEvent, exc)
            except (ValueError, IndexError):
                # The cookie is authenticated, so there was a mistake or a
                # change of settings.
                self._logger.warning(
                    'Authentic session cookie has invalid data (%s).'
                    % cookie_raw
                )
                # Don't use session if we could not unpack renewal_id
                session = None

            if session is not None:
                if not self._is_valid_session(session):
                    self._logger.debug(
                        'Deleting invalid session from the db (%s).'
                        % session.id
                    )
                    self._delete_session(session)
                    session = None
            else:
                # Request has a session cookie, but its value is invalid.
                # Prepare the cookie for removal, unless later it is
                # overwritten with a new session cookie.
                # Since we haven't found any DB entry for the cookie,
                # we don't know if it was set with different path or
                # domain value. We can only guess the values were the same
                # as our defaults.
                self._prepare_delete_cookie_action(
                    name=self._cookie_name,
                    path=self._cookie_path,
                    domain=self._cookie_domain
                )
                self._add_cookie_callback()
        self._init_session_instance(session)
        self._attach_before_commit()
        self._add_vary_callback()

    def _fire_event(self, event_class, exception=None):
        event = event_class(self.request, exception)
        self.request.registry.notify(event)

    def _load_session(self, id):
        """ Load session instance from the database. """
        return self._dbsession.query(self._model_class).get(id)

    def _delete_session(self, session):
        """ Delete session instance from the database """
        if not self._new:
            self._delete_session_cookie(session)
            self._existing_invalidated = True
        self._dbsession.delete(session)

    def _delete_session_cookie(self, session):
        # Don't call add_cookie_callback: it will be called later depending on
        # commit success.
        self._prepare_delete_cookie_action(
            name=self._cookie_name,
            path=self._cookie_path,
            domain=self._cookie_domain
        )

    def _prepare_delete_cookie_action(self, **cookie):
        """ Prepares callable cookie action to delete current session cookie.
        Whether or not it will run depends on cookie callback and survival
        of the action value. """
        def delete_action(response):
            response.delete_cookie(**cookie)
        self._cookie_action = delete_action

    def _init_session_instance(self, session=None):
        """ Initialize existing session ORM instance or a new instance. """
        if session is not None:
            self._logger.info('Initializing existing session %s' % session.id)
            self._new = False
        else:
            self._new = True
            args = self._new_session_args()
            session = self._model_class(**args)
            self._logger.info('Creating new session %s' % session.id)
        self.data = session.data
        self._session = session
        self._dirty = False

    def _new_session_args(self):
        return {
            'id': uuid.UUID(bytes=os.urandom(16)),
            'data': {},
            'flash': {},
            'created': int_now(),
        }

    def _is_valid_session(self, session):
        """ Check if the model instance is valid according to the settings."""
        return True

    def _is_empty_session(self, session):
        """ Check if the model instance contains empty session """
        return len(session.data) == 0 and len(session.flash) == 0

    def _attach_before_commit(self):
        def tm_before_commit():
            self._logger.debug('Running before commit TM hook')
            # Discard unsaved settings if any.
            self.settings.discard()
            s = self._session
            if self.new:
                if self._dirty:
                    if self._is_empty_session(s):
                        self._dirty = False
                    else:
                        self._logger.debug(
                            'Adding new session %s to dbsession' % s.id
                        )
                        self._dbsession.add(s)
                        self._cookieval = s.id.bytes
                        if self.settings.renewal_timeout is not None:
                            self._cookieval += s.renewal_id.bytes
            else:
                # Check if we need to run the renewal procedure.
                if self._config_renewal is not None:
                    self._renewal()

                # Check if we need to force the extension of the session.
                if self._config_idle is not None:
                    self._maybe_extend()

            if self.settings.idle_timeout is not None and self._dirty:
                s.idle_expire = int_now() + self.settings.idle_timeout

            if self.new and (self._dirty or self._existing_invalidated):
                # Txn: insert new session or delete existing.
                self._attach_after_commit()

        txn = self.request.tm.get()
        txn.addBeforeCommitHook(tm_before_commit)

    def _add_cookie_callback(self):
        """ Add response callback to manage Set-Cookie header. """
        if not self._cookie_callback_added:
            self._cookie_callback_added = True

            def cookie_callback(request, response):
                if self._cookie_action is not None:
                    self._cookie_action(response)
            self.request.add_response_callback(cookie_callback)

    def _add_vary_callback(self):
        """ Add response callback to add/modify Vary header. """
        def vary_callback(request, response):
            vary = set() if response.vary is None else set(response.vary)
            vary.add('Cookie')
            response.vary = vary
        self.request.add_response_callback(vary_callback)

    def _attach_after_commit(self):
        """ Add TM 'after commit' callback. """
        def tm_after_commit(status):
            # Don't set cookies on rollbacks. Note: successful read only txn
            # also has status = True.
            if status and (self._dirty or self._existing_invalidated):
                self._logger.debug('Successful TM commit.')
                self._add_cookie_callback()
                if self._new_cookie is not None:
                    def setcookie_action(response):
                        response.set_cookie(**self._new_cookie)
                    self._cookie_action = setcookie_action

        txn = self.request.tm.get()
        txn.addAfterCommitHook(tm_after_commit)
        # Prepare the cookie to set later. Note: we assume after this point no
        # changes will happen to the cookie settings or the payload,
        # because we only call this method once before the commit:
        # - in renewal, it runs for existing sessions only
        # - in _attach_before_commit() - for new session only.
        if self._cookieval is not None:
            self._new_cookie = {
                'name': self._cookie_name,
                'path': self.settings.cookie_path,
                'domain': self.settings.cookie_domain,
                'value': native_(self._serializer.dumps(self._cookieval)),
                'max_age': self.settings.cookie_max_age,
                'secure': self.settings.cookie_secure,
                'httponly': self.settings.cookie_httponly,
            }

    def new_csrf_token(self):
        self._raise_not_implemented('CSRFMixin')

    def get_csrf_token(self):
        self._raise_not_implemented('CSRFMixin')

    @property
    def userid(self):
        self._raise_not_implemented('UseridMixin')

    @userid.setter
    def userid(self, value):
        self._raise_not_implemented('UseridMixin')

    def _raise_not_implemented(self, mixin_name):
        raise NotImplementedError(
            "The API is disabled, because the model does not inherit from %s"
            % mixin_name
        )

    @property
    @initializes_session
    def settings(self):
        if self._settings is None:
            bases = tuple(reversed(self._settings_mixins()))
            cls = type('FrankenSessionSettings', bases, {})
            self._settings = cls(self)
        return self._settings

    @settings.setter
    def settings(self):
        raise NotImplementedError("Can't manually attach settings")

    def _settings_mixins(self):
        return [SessionSettings, _BaseSettings]


class _CSRFSession:
    """ Session mixin to store csrf token. """
    def _is_empty_session(self, session):
        if not super()._is_empty_session(session):
            return False
        return session.csrf_token is None

    @initializes_session
    def new_csrf_token(self):
        self._session.csrf_token = os.urandom(CSRF_TOKEN_SIZE)
        self._dirty = True
        return text_(base64.urlsafe_b64encode(self._session.csrf_token))

    @initializes_session
    def get_csrf_token(self):
        if self._session.csrf_token is None:
            return self.new_csrf_token()
        else:
            return text_(base64.urlsafe_b64encode(self._session.csrf_token))


class _UseridSession:
    """ Session mixin to store userid explicitly. """
    def _is_empty_session(self, session):
        if not super()._is_empty_session(session):
            return False
        return session.userid is None

    userid = SessionProperty('userid')


class _RenewalSession:
    """ Session mixin to implement Renewal Timeout security policy. """
    def _is_valid_session(self, session):
        # First check parent votes. Note: we always want to run our checks
        # here to detect renewal violations even if the session is invalid
        # for other reasons.
        default = super()._is_valid_session(session)

        # Check if the policy is enabled at all.
        if self._config_renewal is None:
            return default

        # Check if the policy is enabled for this session.
        if self._config_renewal:
            renewal_timeout = session.renewal_timeout
        else:
            renewal_timeout = self._renewal_timeout
        if renewal_timeout is None:
            return default

        if self._renewal_id != session.renewal_id:
            if (session.renewal_next is None or
                self._renewal_id != session.renewal_next):

                self._logger.warning(
                    "Invalid renewal id found in the cookie of session %s"
                    % session.id
                )
                self._fire_event(RenewalViolationEvent)
                return False
        return default

    def _new_session_args(self):
        now = int_now()
        args = super()._new_session_args()
        args['renewal_id'] = uuid.UUID(bytes=os.urandom(16))
        args['renewed'] = now
        args['renewal_tried'] = now
        return args

    def _renewal(self):
        """ Run procedures to implement renewal timeout policy. """
        if self.settings.renewal_timeout is None:
            return

        now = int_now()
        s = self._session
        if now - s.renewed < self.settings.renewal_timeout:
            return

        def _try_renew(s):
            next_bytes = os.urandom(16)
            s.renewal_next = uuid.UUID(bytes=next_bytes)
            s.renewal_tried = now
            self._dirty = True
            self._cookieval = s.id.bytes + next_bytes
            self._attach_after_commit()

        if s.renewal_next is None:
            # Start renewal
            self._logger.debug('Trying to renew session %s' % s.id)
            _try_renew(s)
        else:
            # We are in the middle of the procedure.
            if self._renewal_id == s.renewal_id:
                # We have tried to set new id, but haven't
                # received the acknowledgement yet. We may need
                # to try again.
                since_try = now - s.renewal_tried
                if since_try > self.settings.renewal_try_every:
                    self._logger.debug(
                        "Renewal try timed out. Trying again"
                        " to renew session %s"
                        % s.id
                    )
                    _try_renew(s)
            else:
                self._logger.debug(
                    "Received ack of the new renewal id."
                    " Finishing renewal of session %s" % s.id
                )
                s.renewal_id = s.renewal_next
                s.renewal_next = None
                s.renewed = now
                self._dirty = True


class _IdleSession:
    """ Session mixin to implement Idle Timeout security policy. """

    def _is_valid_session(self, session):
        # Check parent votes. If a parent votes False there's not much use to
        # run our checks here.
        if not super()._is_valid_session(session):
            return False

        # Check if the policy is enabled at all.
        if self._config_idle is None:
            return True

        # Check if the policy is enabled for this session.
        if self._config_idle:
            idle_timeout = session.idle_timeout
        else:
            idle_timeout = self._idle_timeout
        if idle_timeout is None:
            return True

        # It's developer's duty to explicitly invalidate existing sessions or
        # to initialize the expiration column prior to enabling the idle
        # timeout policy. Also, when directly manipulating DB data, it's
        # developer's duty to make sure the result is sane.
        if session.idle_expire is None:
            raise InconsistentDataError(
                "Session idle timeout is enabled, but idle_expire"
                " timestamp value is None: %s." % session.id
            )

        if int_now() > session.idle_expire:
            self._logger.info(
                'Session has reached idle timeout: %s.' % session.id
            )
            return False
        return True

    def _new_session_args(self):
        args = super()._new_session_args()
        if self._idle_timeout is not None:
            args['idle_expire'] = int_now() + self._idle_timeout
        return args

    def _maybe_extend(self):
        """ If the existing session is not dirty, check if we need to
        force the update of the 'idle_expire' column. """
        if self._dirty or self.settings.idle_timeout is None:
            return

        s = self._session
        accessed = s.idle_expire - self.settings.idle_timeout
        since_access = int_now() - accessed
        past_delay = (self.settings.extension_delay is None or
                      since_access > self.settings.extension_delay)
        if past_delay:
            force_update = (since_access > self.settings.extension_deadline or
                            weighted_truth(self.settings.extension_chance))
            if force_update:
                self._logger.debug(
                    "Forcing update of 'idle_expire' column for"
                    " otherwise clean session %s" % s.id
                )
                # Marking it dirty will trigger the extension.
                self._dirty = True


class _AbsoluteSession:
    """ Session mixin to implement Absolute Timeout security policy. """

    def _is_valid_session(self, session):
        # Check parent votes. If a parent votes False there's not much use to
        # run our checks here.
        if not super()._is_valid_session(session):
            return False

        # Check if the policy is enabled at all.
        if self._config_absolute is None:
            return True

        # Check if the policy is enabled for this session.
        if self._config_absolute:
            absolute_timeout = session.absolute_timeout
        else:
            absolute_timeout = self._absolute_timeout
        if absolute_timeout is None:
            return True

        if int_now() > session.absolute_expire:
            self._logger.info(
                'Session has reached absolute timeout: %s.' % session.id
            )
            return False
        return True


class _ConfigCookieSession:
    """ Session mixin to manage per-session cookie settings. """
    def _new_session_args(self):
        args = super()._new_session_args()
        for name in ('cookie_max_age', 'cookie_path', 'cookie_domain',
                     'cookie_secure', 'cookie_httponly'):
            args[name] = getattr(self, '_' + name)
        return args

    def _delete_session_cookie(self, session):
        self._prepare_delete_cookie_action(
            name=self._cookie_name,
            path=session.cookie_path,
            domain=session.cookie_domain
        )

    def _settings_mixins(self):
        mixins = super()._settings_mixins()
        mixins.append(_ConfigCookieSettings)
        return mixins


class _ConfigIdleSession(_IdleSession):
    """ Session mixin that makes idle timeout configurable at runtime. """
    def _new_session_args(self):
        args = super()._new_session_args()
        for name in ('idle_timeout', 'extension_delay', 'extension_chance',
                     'extension_deadline'):
            args[name] = getattr(self, '_' + name)
        return args

    def _settings_mixins(self):
        mixins = super()._settings_mixins()
        mixins.append(_ConfigIdleSettings)
        return mixins


class _ConfigAbsoluteSession(_AbsoluteSession):
    """ Session mixin that makes absolute timeout configurable at runtime. """
    def _new_session_args(self):
        args = super()._new_session_args()
        if self._absolute_timeout is not None:
            args['absolute_expire'] = int_now() + self._absolute_timeout
        return args

    def _settings_mixins(self):
        mixins = super()._settings_mixins()
        mixins.append(_ConfigAbsoluteSettings)
        return mixins


class _ConfigRenewalSession(_RenewalSession):
    """ Session mixin that makes renewal timeout configurable at runtime. """
    def _new_session_args(self):
        args = super()._new_session_args()
        args['renewal_timeout'] = self._renewal_timeout
        args['renewal_try_every'] = self._renewal_try_every
        return args

    def _settings_mixins(self):
        mixins = super()._settings_mixins()
        mixins.append(_ConfigRenewalSettings)
        return mixins
