import pytest
import hypothesis.strategies as st
from hypothesis import (
    given,
    assume,
)

from ..config.validators import MAX_INTEGER
from .contexts import (
    new_context,
    new_request,
)
from .strategies import (
    pickles,
    shared_config,
    stable_extension_settings,
    unstable_extension_settings,
    valid_model_class,
    valid_settings,
)


def assert_same_session(request, id, marker='test'):
    """ Given the original session id and a marker, assert that request session
    is the same session. """
    assert not request.session.new
    assert marker in request.session
    assert id == request.session._session.id


def assert_new_session(request, id, marker='test'):
    """ Given the original session id and a marker, assert that request session
    is a new session. """
    assert request.session.new 
    assert marker not in request.session
    assert id != request.session._session.id


def set_check_new_settings(context, settings, names):
    """ Given context, try to set names from settings. Check that new settings
    are active. """
    with new_request(context) as request:
        request.session['test'] = 1
        with request.session.settings as s:
            for name in names:
                s[name] = settings[name]
    with new_request(context) as request:
        for name in names:
            assert request.session.settings[name] == settings[name]


def test_selftest_context_manages_cookies(minimal_context):
    with new_request(minimal_context) as request:
        request.session['test'] = 1
    with new_request(minimal_context) as request:
        assert 'session' in request.cookies


def test_disabled_features_raise_not_implemented(minimal_context):
    with new_request(minimal_context) as request:
        session = request.session
        with pytest.raises(NotImplementedError):
            request.session.new_csrf_token()
        with pytest.raises(NotImplementedError):
            request.session.get_csrf_token()    
        with pytest.raises(NotImplementedError):
            userid = request.session.userid
        with pytest.raises(NotImplementedError):
            request.session.userid = 1


@given(settings=valid_settings())
def test_class_implements_ISession(settings):
    from zope.interface.verify import verifyClass
    from pyramid.interfaces import ISession
    from pyramid.util import DottedNameResolver
    from ..session import get_session_factory
    from ..config import factory_args_from_settings
    args = factory_args_from_settings(
        settings,
        DottedNameResolver().maybe_resolve,
        '',
    )
    factory = get_session_factory(**args)
    verifyClass(ISession, factory)


@given(settings=valid_settings())
def test_instance_implements_ISession(settings):
    from zope.interface.verify import verifyObject
    from pyramid.interfaces import ISession
    with new_context(settings) as context:
        with new_request(context) as request:
            verifyObject(ISession, request.session)


@given(
    settings=valid_settings(),
    shared=shared_config(),
)
def test_session_matches_orm_mixins(settings, shared):
    from ..session import (
        _UseridSession,
        _CSRFSession,
        _ConfigCookieSession,
        _ConfigRenewalSession,
        _RenewalSession,
        _ConfigIdleSession,
        _IdleSession,
        _ConfigAbsoluteSession,
        _AbsoluteSession,
        )
    with new_context(settings) as context:
        with new_request(context) as request:
            request.session['x'] = 1
            s = request.session
            if shared['enable_userid']:
                assert isinstance(s, _UseridSession)
            if shared['enable_csrf']:
                assert isinstance(s, _CSRFSession)
            if shared['enable_configcookie']:
                assert isinstance(s, _ConfigCookieSession)
            mixin_config_features = {
                'config_renewal': (_ConfigRenewalSession, _RenewalSession),
                'config_idle': (_ConfigIdleSession, _IdleSession),
                'config_absolute': (_ConfigAbsoluteSession, _AbsoluteSession),
            }
            for c, m in mixin_config_features.items():
                if shared[c] is None:
                    assert not (isinstance(s, m[0]) or isinstance(s, m[1]))
                if shared[c] is True:
                    assert isinstance(s, m[0]) and isinstance(s, m[1])
                if shared[c] is False:
                    assert isinstance(s, m[1]) and not isinstance(s, m[0])


@given(settings=valid_settings())
def test_lazy_session(settings):
    with new_context(settings) as context:
        with new_request(context) as request:
            assert getattr(request.session, '_session', None) == None
        with new_request(context) as request:
            assert 'test' not in request.session
            id = request.session._session.id
        with new_request(context) as request:
            assert_new_session(request, id)
            request.session['test'] = 1
            id = request.session._session.id
        with new_request(context) as request:
            assert_same_session(request, id)
            request.session.invalidate()
            assert_new_session(request, id)
            id2 = request.session._session.id
        with new_request(context) as request:
            assert_new_session(request, id)
            assert_new_session(request, id2)


@pytest.mark.xfail(reason="May need some tweaking based on dialect.")
@pytest.mark.parametrize(
    'isolation_level',
    (
        'READ_UNCOMMITTED',
        'READ_COMMITTED',
        'REPEATABLE_READ',
        'SERIALIZABLE',
    ),
)
def test_concurrency(minimal_settings, isolation_level):
    """ A small exercise on db isolation levels in the session context. """
    settings = minimal_settings

    def different_dbs(*requests):
        return len(set([r.dbsession for r in requests])) == len(requests)

    with new_context(settings) as context:
        dialect_name = context.engine.dialect.name
        # sqlite has very poor support for concurrency, specially in the
        # in-memory mode.
        if dialect_name == 'sqlite':
            pytest.skip()

    from sqlalchemy.exc import OperationalError

    # 1 write and reads.
    with new_context(settings, isolation_level=isolation_level) as context:
        with new_request(context) as request:
            request.session['test'] = 1
            id = request.session._session.id
        with new_request(context) as request1:
            # We have to read something to start the transaction, but to avoid
            # initializing the session.
            request1.dbsession.query(settings['model_class']).first()
            with new_request(context) as request2:
                assert_same_session(request2, id)
                request2.session['test'] = 2
                request2.dbsession.flush()
                with new_request(context) as request3:
                    assert_same_session(request3, id)
                    assert different_dbs(request1, request2, request3)
                    # Dirty Read. Should be 2 with "read uncommitted",
                    # but not in PostgreSQL.
                    if (isolation_level == 'READ_UNCOMMITTED' 
                        and dialect_name != 'postgresql'):
                        assert request3.session['test'] == 2
                    else:
                        assert request3.session['test'] == 1
            # Nonrepeatable Read. Should be 2 with "read committed" and below.
            assert_same_session(request1, id)
            if isolation_level in ('READ_UNCOMMITTED', 'READ_COMMITTED'):
                assert request1.session['test'] == 2
            else:
                assert request1.session['test'] == 1
        with new_request(context) as request1:
            assert request1.session['test'] == 2

    # 2 writes.
    with new_context(settings, isolation_level=isolation_level) as context:
        with new_request(context) as request:
            request.session['test'] = 1
            id = request.session._session.id

        def may_not_serialize():
            with new_request(context) as request1:
                assert_same_session(request1, id)
                with new_request(context) as request2:
                    assert_same_session(request2, id)
                    assert different_dbs(request1, request2)
                    request2.session['test'] = 2
                request1.session['test'] = 3

        if isolation_level in ('SERIALIZABLE', 'REPEATABLE_READ'):
            # Outer txn should fail.
            with pytest.raises(OperationalError):
                may_not_serialize()
            with new_request(context) as request:
                assert request.session['test'] == 2
        else:
            may_not_serialize()
            with new_request(context) as request:
                assert request.session['test'] == 3


@given(settings=valid_settings())
def test_isession_created_new(settings):
    with new_context(settings) as context:
        time = context.time
        with new_request(context) as request:
            request.session['test'] = 1
            assert request.session.new
            with pytest.raises(NotImplementedError):
                request.session.new = False
        with new_request(context) as request:
            assert request.session.created == time
            assert not request.session.new


@given(settings=valid_settings())
def test_isession_changed(settings):
    with new_context(settings) as context:
        with new_request(context) as request:
            request.session['box'] = set() 
        with new_request(context) as request:
            assert 'box' in request.session
            request.session['box'].add('cat')
        with new_request(context) as request:
            assert 'cat' not in request.session['box']
            request.session['box'].add('cat')
            request.session.changed()
        with new_request(context) as request:
            assert 'cat' in request.session['box']


@given(settings=valid_settings())
def test_isession_invalidate(settings):
    with new_context(settings) as context:
        with new_request(context) as request:
            request.session['test'] = 1
            id = request.session._session.id
        with new_request(context) as request:
            assert_same_session(request, id)
            request.session.invalidate()
            assert len(request.session.items()) == 0
            assert_new_session(request, id)
        with new_request(context) as request:
            assert_new_session(request, id)


@given(
    settings=valid_settings(),
    messages=st.lists(elements=st.text(max_size=255), min_size=1, max_size=8),
    queue=st.one_of(st.none(), st.text(max_size=64)),
    wrong_queue=st.text(max_size=64),
    allow_duplicate=st.sampled_from((True, False, None)),
)
def test_isession_flash(
    settings,
    messages,
    queue,
    wrong_queue,
    allow_duplicate,
    ):
    assume(wrong_queue != queue)
    assume(not (wrong_queue == '' and queue is None))
    q_args = {} if queue is None else {'queue': queue}
    flash_args = q_args.copy()
    if allow_duplicate is not None:
        flash_args.update({'allow_duplicate': allow_duplicate})
    unique_set = set(messages)
    has_duplicates = len(unique_set) < len(messages)
    with new_context(settings) as context:
        with new_request(context) as request:
            for msg in messages:
                request.session.flash(msg, **flash_args)
        with new_request(context) as request:
            assert len(request.session.peek_flash(wrong_queue)) == 0
            peeked = request.session.peek_flash(**q_args).copy()
            assert len(peeked) != 0
            popped = request.session.pop_flash(**q_args)
            assert len(request.session.peek_flash(**q_args)) == 0
            assert peeked == popped
            if has_duplicates:
                if allow_duplicate is None or allow_duplicate:
                    assert messages == popped
                else:
                    assert len(unique_set) == len(popped)
                    assert unique_set == set(popped)
        with new_request(context) as request:
            assert len(request.session.peek_flash(**q_args)) == 0


@given(
    settings=valid_settings(),
    value=pickles(),
    newvalue=pickles(),
)
def test_isession_dict(settings, value, newvalue):
    assume(value != newvalue)
    import collections.abc
    with new_context(settings) as context:
        with new_request(context) as request:
            request.session['value'] = value
        # get
        with new_request(context) as request:
            assert value == request.session.get('value')
        # __getitem__
        with new_request(context) as request:
            assert value == request.session['value']
        # items
        with new_request(context) as request:
            items = request.session.items()
            assert len(items) == 1
            assert ('value', value) in items
            from_iter = [(k, v) for k, v in items]
            assert [(k, v) for k, v in items] == [('value', value)]
        # keys
        with new_request(context) as request:
            keys = request.session.keys()
            assert len(keys) == 1
            assert 'value' in keys
            assert [k for k in keys] == ['value']
            assert isinstance(keys, collections.abc.Set)
        # values
        with new_request(context) as request:
            values = request.session.values()
            assert len(values) == 1
            assert value in values
            assert [v for v in values] == [value]
        # __contains__
        with new_request(context) as request:
            assert 'value' in request.session
            assert 'garbage' not in request.session
        # __len__
        with new_request(context) as request:
            assert len(request.session) == 1
        # __iter__
        with new_request(context) as request:
            assert [k for k in request.session] == ['value']

    with new_context(settings) as context:
        # clear
        with new_request(context) as request:
            request.session['value'] = value
            id = request.session._session.id
        with new_request(context) as request:
            assert_same_session(request, id, 'value')
            request.session.clear()
            assert not request.session.new
            assert len(request.session) == 0
        with new_request(context) as request:
            assert not request.session.new
            assert id == request.session._session.id
            assert len(request.session) == 0

    with new_context(settings) as context:
        # update
        with new_request(context) as request:
            request.session['value'] = value
            id = request.session._session.id
        with new_request(context) as request:
            assert_same_session(request, id, 'value')
            request.session.update({'value': newvalue})
            assert request.session['value'] == newvalue
        with new_request(context) as request:
            assert request.session['value'] == newvalue

    with new_context(settings) as context:
        # setdefault
        with new_request(context) as request:
            request.session['value'] = value
            id = request.session._session.id
        with new_request(context) as request:
            assert newvalue == request.session.setdefault('newvalue', newvalue)
            assert value == request.session.setdefault('value', newvalue)
        with new_request(context) as request:
            assert request.session['value'] == value
            assert request.session['newvalue'] == newvalue

    with new_context(settings) as context:
        # pop
        def assert_pop_empty():
            assert len(request.session) == 0
            assert newvalue == request.session.pop('value', newvalue)
            with pytest.raises(KeyError):
                request.session.pop('value')
                
        with new_request(context) as request:
            request.session['value'] = value
            id = request.session._session.id
        with new_request(context) as request:
            assert value == request.session.pop('value', newvalue)
            assert_pop_empty()
        with new_request(context) as request:
            assert_pop_empty()
            assert id == request.session._session.id

    with new_context(settings) as context:
        # popitem
        def assert_popitem_empty():
            assert len(request.session) == 0
            with pytest.raises(KeyError):
                request.session.popitem()

        with new_request(context) as request:
            request.session['value'] = value
            id = request.session._session.id
        with new_request(context) as request:
            assert ('value', value) == request.session.popitem()
            assert_popitem_empty()
        with new_request(context) as request:
            assert_popitem_empty()
            assert id == request.session._session.id

    with new_context(settings) as context:
        # __delitem__
        with new_request(context) as request:
            request.session['value'] = value
            id = request.session._session.id
        with new_request(context) as request:
            assert_same_session(request, id, 'value')
            del request.session['value']
            assert 'value' not in request.session
        with new_request(context) as request:
            assert 'value' not in request.session
            assert id == request.session._session.id


@given(
    settings=valid_settings(),
    shared=shared_config().filter(lambda s: s['enable_csrf']),
)
def test_csrf(settings, shared):
    import base64
    from pyramid.compat import bytes_
    from ..model import CSRF_TOKEN_SIZE
    def valid_token(token):
        t_bytes = base64.urlsafe_b64decode(bytes_(token))
        return len(t_bytes) == CSRF_TOKEN_SIZE

    with new_context(settings) as context:
        with new_request(context) as request:
            token = request.session.get_csrf_token()
            assert valid_token(token)
        with new_request(context) as request:
            assert token == request.session.get_csrf_token()
            new_token = request.session.new_csrf_token()
            assert valid_token(new_token)
            assert token != new_token
        with new_request(context) as request:
            assert new_token == request.session.get_csrf_token()


@given(
    settings=valid_settings(),
    shared=shared_config().filter(lambda s: s['enable_userid']),
    value=st.integers(min_value=0, max_value=MAX_INTEGER),
)
def test_userid(settings, shared, value):
    with new_context(settings) as context:
        with new_request(context) as request:
            request.session.userid = value
        with new_request(context) as request:
            assert request.session.userid == value
            request.session.userid = None
        with new_request(context) as request:
            assert request.session.userid is None


@given(
    settings=valid_settings(),
    shared=shared_config(),
    new_settings=valid_settings(),
)
def test_renewal_timeout(settings, shared, new_settings):
    check_settings = [settings]
    names = (
        'renewal_timeout',
        'renewal_try_every',
    )
    if shared['config_renewal']:
        check_settings.append(new_settings)
        for name in names:
            assume(settings[name] != new_settings[name])
    for s in check_settings:
        assume(s['absolute_timeout'] is None)
        assume(s['idle_timeout'] is None)
        assume(s['renewal_timeout'])
        # Allow some gap.
        assume(s['renewal_timeout'] > 2)
        assume(s['cookie_max_age'] is None)

    from ..events import RenewalViolationEvent

    with new_context(settings) as context:
        if shared['config_renewal']:
            set_check_new_settings(context, new_settings, names)
        with new_request(context) as request:
            request.session['test'] = 1
            id = request.session._session.id
            renewal_timeout = request.session.settings.renewal_timeout
            renewal_try_every = request.session.settings.renewal_try_every
        context.time += renewal_timeout - 1
        start_cookies = context._cookies.copy()
        with new_request(context) as request:
            assert_same_session(request, id)
        assert context._cookies == start_cookies
        context.time += 2
        with new_request(context) as request:
            assert_same_session(request, id)
        assert context._cookies != start_cookies
        # Simulate failed renewal try.
        context._cookies = start_cookies
        context.time += renewal_try_every - 1
        with new_request(context) as request:
            assert_same_session(request, id)
        assert context._cookies == start_cookies
        context.time += 2
        with new_request(context) as request:
            assert_same_session(request, id)
        assert context._cookies != start_cookies
        with new_request(context) as request:
            assert_same_session(request, id)
        # Finished renewal. Simulate stolen cookie.
        event_fired = False
        def renewal_violation_subscriber(event):
            # Maybe check something ?
            nonlocal event_fired
            event_fired = True
        context.config.add_subscriber(
            renewal_violation_subscriber,
            RenewalViolationEvent,
        )
        context._cookies = start_cookies
        with new_request(context) as request:
            assert_new_session(request, id)
        assert event_fired is True


@given(
    settings=stable_extension_settings(),
    shared=shared_config(),
    new_settings=stable_extension_settings(),
)
def test_idle_timeout(settings, shared, new_settings):
    check_settings = [settings]    
    names = (
        'idle_timeout',
        'extension_delay',
        'extension_chance', 
        'extension_deadline',
    )
    if shared['config_idle']:
        check_settings.append(new_settings)
        for name in names:
            assume(settings[name] != new_settings[name])
    for s in check_settings:
        assume(s['absolute_timeout'] is None)
        assume(s['idle_timeout'])
        # Allow some gap.
        assume(s['idle_timeout'] > 2)
        assume(s['cookie_max_age'] is None)

    with new_context(settings) as context:
        if shared['config_idle']:
            set_check_new_settings(context, new_settings, names)
        with new_request(context) as request:
            request.session['test'] = 1
            id = request.session._session.id
            extension_delay = request.session.settings.extension_delay
            idle_timeout = request.session.settings.idle_timeout

        if extension_delay is not None:
            # Demonstrate the delay.
            will_expire_at = context.time + idle_timeout + 1
            context.time += extension_delay - 1
            with new_request(context) as request:
                assert_same_session(request, id)
            context.time = will_expire_at
            with new_request(context) as request:
                # New session because we haven't extended the old one.
                assert_new_session(request, id)
            # Try again, but trigger session write before delay.
            if shared['config_idle']:
                set_check_new_settings(context, new_settings, names)
            with new_request(context) as request:
                request.session['test'] = 1
                id = request.session._session.id
            will_expire_at = context.time + idle_timeout + 1
            context.time += extension_delay - 1
            with new_request(context) as request:
                assert_same_session(request, id)
                # Writes always extend.
                request.session['test'] = 2
            context.time = will_expire_at
            with new_request(context) as request:
                # Same session because of the write.
                assert_same_session(request, id)
                request.session.invalidate()
            if shared['config_idle']:
                set_check_new_settings(context, new_settings, names)
        # Test normal extension.
        with new_request(context) as request:
            request.session['test'] = 1
            id = request.session._session.id
            extend_after = idle_timeout
        will_expire_at = context.time + idle_timeout + 1
        context.time += extend_after
        with new_request(context) as request:
            # Normal extension.
            assert_same_session(request, id)
        context.time = will_expire_at
        with new_request(context) as request:
            # Not expired because of extension
            assert_same_session(request, id)
            request.session.invalidate()
        # Test no extension.
        if shared['config_idle']:
            set_check_new_settings(context, new_settings, names)
        with new_request(context) as request:
            request.session['test'] = 1
            id = request.session._session.id
        context.time += idle_timeout + 1
        with new_request(context) as request:
            assert_new_session(request, id)


@given(
    settings=unstable_extension_settings(),
    shared=shared_config(),
    new_settings=unstable_extension_settings(),
)
def test_idle_unstable_extension(settings, shared, new_settings):
    # It's not clear how to test extension chance properly without making
    # too many requests. Atleast we can test that extension fails sometimes,
    # and reaching deadline always extends.
    check_settings = [settings]
    names = (
        'idle_timeout',
        'extension_delay',
        'extension_chance', 
        'extension_deadline',
    )
    if shared['config_idle']:
        check_settings.append(new_settings)
        for name in names:
            assume(settings[name] != new_settings[name])
    for s in check_settings:
        assume(s['absolute_timeout'] is None)
        assume(s['idle_timeout'])
        # Allow some gap for many extension tries.
        assume(s['idle_timeout'] > 100)
        assume(s['cookie_max_age'] is None)
        assume(s['extension_delay'] is None)

    with new_context(settings) as context:
        if shared['config_idle']:
            set_check_new_settings(context, new_settings, names)
        with new_request(context) as request:
            request.session['test'] = 1
            id = request.session._session.id
        with new_request(context) as request:
            assert_same_session(request, id)
            will_expire_at = context.time + \
                request.session.settings.idle_timeout
            assert request.session._session.idle_expire == will_expire_at
            deadline = context.time + \
                request.session.settings.extension_deadline
        # Try to extend until success or max_tries reached.
        extended = False
        tries = 1
        max_tries = 2
        while(not extended and tries <= max_tries):
            context.time += 1
            with new_request(context) as request:
                # This may extend or not.
                assert_same_session(request, id)
            with new_request(context) as request:
                assert_same_session(request, id)
                if request.session._session.idle_expire > will_expire_at:
                    extended = True
            tries += 1
        if not extended:
            context.time = deadline + 1
            with new_request(context) as request:
                assert_same_session(request, id)
        context.time = will_expire_at + 1
        with new_request(context) as request:
            assert_same_session(request, id)


@given(
    settings=valid_settings(),
    shared=shared_config(),
    new_settings=valid_settings(),
)
def test_absolute_timeout(settings, shared, new_settings):
    check_settings = [settings]
    names = ('absolute_timeout',)
    if shared['config_absolute']:
        check_settings.append(new_settings)
        assume(
            settings['absolute_timeout'] != new_settings['absolute_timeout']
        )
    for s in check_settings:
        assume(s['idle_timeout'] is None)
        assume(s['absolute_timeout'])
        # Allow some gap.
        assume(s['absolute_timeout'] > 1)
        assume(s['cookie_max_age'] is None)

    with new_context(settings) as context:
        if shared['config_absolute']:
            set_check_new_settings(context, new_settings, names)
        with new_request(context) as request:
            request.session['test'] = 1
            id = request.session._session.id
            absolute_timeout = request.session.settings.absolute_timeout
        context.time += absolute_timeout - 1
        with new_request(context) as request:
            assert_same_session(request, id)
        context.time += 2
        with new_request(context) as request:
            assert_new_session(request, id)


@given(
    settings=valid_settings(),
    shared=shared_config(),
    new_settings=valid_settings(),
)
def test_cookie(settings, shared, new_settings):
    names = (
        'cookie_max_age',
        'cookie_path',
        'cookie_domain', 
        'cookie_secure',
        'cookie_httponly',
    )
    if shared['enable_configcookie']:
        for name in names:
            assume(settings[name] != new_settings[name])
    with new_context(settings) as context:
        if shared['enable_configcookie']:
            set_check_new_settings(context, new_settings, names)
        else:
            new_settings = settings
            with new_request(context) as request:
                request.session['test'] = 1
        key = (
            settings['cookie_name'],
            new_settings['cookie_path'],
            new_settings['cookie_domain'],
        )
        value = context._cookies[key]
        if new_settings['cookie_max_age'] is None:
            expire = None
        else:
            expire = context.time + new_settings['cookie_max_age']
        assert value[1] == expire
        assert value[2] == new_settings['cookie_secure']
        assert value[3] == new_settings['cookie_httponly']
