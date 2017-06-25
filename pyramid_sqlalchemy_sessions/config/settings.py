from collections.abc import MutableMapping

from ..config import (
    _validate_config_settings,
    RUNTIME_SETTINGS,
)
from ..exceptions import SettingsError
from ..util import int_now
from .validators import _validate_int_none


class SessionSetting():
    def __init__(self, name):
        self.name = name

    def __get__(self, settings, type=None):
        # Return unsaved values also, to not confuse the caller (read your
        # own writes).
        return settings._dirty.get(
            self.name,
            getattr(settings.session._session, self.name)
        )

    def __set__(self, settings, value):
        if settings._locked:
            raise SettingsError(
                "Put settings in editable mode to change it."
            )
        settings._dirty[self.name] = value


class FixedSetting(SessionSetting):
    def __get__(self, settings, type=None):
        return getattr(settings.session, '_' + self.name)

    def __set__(self, settings, value):
        raise SettingsError(
            "The setting is not configurable at runtime. Subclass your model"
            " from the corresponding Config*Mixin if you want to change it."
        )


class IdleTimeoutSetting(SessionSetting):
    def __set__(self, settings, value):
        super().__set__(settings, value)
        # We have to validate here, because _dirty dict will be saved without
        # a way to inject additional callback.
        try:
            validated = _validate_int_none('idle_timeout', value)
            if validated is None:
                settings._dirty['idle_expire'] = None
            else:
                settings._dirty['idle_expire'] = int_now() + value
        except ValueError:
            pass


class SessionSettings(MutableMapping):
    def __init__(self, session):
        self.session = session
        self._dirty = {}
        self._locked = True

    def __enter__(self):
        self.edit()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not exc_value:
            self.save()

    def edit(self):
        """ Put settings in editable mode. """
        if not self.session.new:
            raise SettingsError(
                "Settings can be changed only for a new session."
            )
        self._locked = False

    def save(self):
        """ Save edited settings. """
        self._validate()
        # Dump whatever is in the dirty dict, so that we can update
        # non-setting values also.
        for k, v in self._dirty.items():
            setattr(self.session._session, k, v)
        self._dirty.clear()
        self._locked = True

    def discard(self):
        """ Discard any non-saved settings changes. """
        self._dirty.clear()
        self._locked = True

    def _validate(self):
        validated = _validate_config_settings(self)
        for name in self._dirty.keys():
            self._dirty[name] = validated.get(name, self._dirty[name])

    # MutableMapping methods.
    def __getitem__(self, key):
        if key not in RUNTIME_SETTINGS:
            raise KeyError()
        return getattr(self, key)

    def __setitem__(self, key, value):
        if key not in RUNTIME_SETTINGS:
            raise KeyError()
        setattr(self, key, value)

    def __delitem__(self, key):
        raise NotImplementedError('Mapping size is fixed.')

    def __iter__(self):
        return RUNTIME_SETTINGS.__iter__()

    def __len__(self):
        return len(RUNTIME_SETTINGS)


class _BaseSettings():
    cookie_max_age = FixedSetting('cookie_max_age')
    cookie_path = FixedSetting('cookie_path')
    cookie_domain = FixedSetting('cookie_domain')
    cookie_secure = FixedSetting('cookie_secure')
    cookie_httponly = FixedSetting('cookie_httponly')
    idle_timeout = FixedSetting('idle_timeout')
    absolute_timeout = FixedSetting('absolute_timeout')
    renewal_timeout = FixedSetting('renewal_timeout')
    renewal_try_every = FixedSetting('renewal_try_every')
    extension_delay = FixedSetting('extension_delay')
    extension_chance = FixedSetting('extension_chance')
    extension_deadline = FixedSetting('extension_deadline')


class _ConfigCookieSettings():
    cookie_max_age = SessionSetting('cookie_max_age')
    cookie_path = SessionSetting('cookie_path')
    cookie_domain = SessionSetting('cookie_domain')
    cookie_secure = SessionSetting('cookie_secure')
    cookie_httponly = SessionSetting('cookie_httponly')


class _ConfigIdleSettings():
    idle_timeout = IdleTimeoutSetting('idle_timeout')
    extension_delay = SessionSetting('extension_delay')
    extension_chance = SessionSetting('extension_chance')
    extension_deadline = SessionSetting('extension_deadline')


class _ConfigAbsoluteSettings():
    absolute_timeout = SessionSetting('absolute_timeout')


class _ConfigRenewalSettings():
    renewal_timeout = SessionSetting('renewal_timeout')
    renewal_try_every = SessionSetting('renewal_try_every')
