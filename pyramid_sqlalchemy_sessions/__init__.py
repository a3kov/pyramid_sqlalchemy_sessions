from .authn import UserSessionAuthenticationPolicy
from .config import (
    factory_args_from_settings,
    generate_secret_key,
)
from .events import (
    CookieCryptoErrorEvent,
    InvalidCookieErrorEvent,
    RenewalViolationEvent,
)
from .exceptions import (
    ConfigurationError,
    CookieCryptoError,
    InconsistentDataError,
    InvalidCookieError,
    SettingsError,
)
from .model import (
    AbsoluteMixin,
    BaseMixin,
    CSRFMixin,
    ConfigAbsoluteMixin,
    ConfigCookieMixin,
    ConfigIdleMixin,
    ConfigRenewalMixin,
    FullyFeaturedSession,
    IdleMixin,
    RenewalMixin,
    UseridMixin,
)
from .session import get_session_factory


__all__ = ['factory_args_from_settings', 'generate_secret_key',
           'get_session_factory', 'UserSessionAuthenticationPolicy',
           'FullyFeaturedSession', 'AbsoluteMixin', 'BaseMixin', 'CSRFMixin',
           'ConfigAbsoluteMixin', 'ConfigCookieMixin', 'ConfigIdleMixin',
           'ConfigRenewalMixin', 'IdleMixin', 'RenewalMixin', 'UseridMixin',
           'CookieCryptoErrorEvent', 'InvalidCookieErrorEvent',
           'RenewalViolationEvent', 'ConfigurationError', 'CookieCryptoError',
           'InconsistentDataError', 'InvalidCookieError', 'SettingsError']


def includeme(config):
    args = factory_args_from_settings(
        config.registry.settings,
        config.maybe_dotted
    )
    session_factory = get_session_factory(**args)
    config.set_session_factory(session_factory)
