import base64
import os
from pyramid.compat import (
    bytes_,
    text_,
)
from sqlalchemy import inspect
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.orm.mapper import Mapper
from ..serializer import (
    AESGCMBytestore,
    SECRET_SIZES,
)
from ..exceptions import ConfigurationError
from ..model import (
    AbsoluteMixin,
    BaseMixin,
    CSRFMixin,
    ConfigAbsoluteMixin,
    ConfigCookieMixin,
    ConfigIdleMixin,
    ConfigRenewalMixin,
    IdleMixin,
    RenewalMixin,
    UseridMixin,
)
from .validators import (
    _validate_asbool,
    _validate_cookie_domain,
    _validate_cookie_path,
    _validate_gt,
    _validate_int_none,
    _validate_nonzero_percent,
    _validate_positive_smallint,
    _validate_prob_extension,
    _validate_python_id,
    _validate_rfc2616_token,
    _validate_smallint_none,
)


def get_config_defaults():
    return {
        'dbsession_name': 'dbsession',
        'cookie_name': 'session',
        'cookie_max_age': None,
        'cookie_path': "/",
        'cookie_domain': None,
        'cookie_secure': False,
        'cookie_httponly': True,
        'idle_timeout': None,
        'absolute_timeout': None,
        'renewal_timeout': None,
        'renewal_try_every': 5,
        'extension_delay': None,
        'extension_chance': 100,
        'extension_deadline': 1,
    }


RUNTIME_SETTINGS = (
    'cookie_max_age',
    'cookie_path',
    'cookie_domain',
    'cookie_secure',
    'cookie_httponly',
    'idle_timeout',
    'absolute_timeout',
    'renewal_timeout',
    'renewal_try_every',
    'extension_delay',
    'extension_chance',
    'extension_deadline',
)


def generate_secret_key(size=32):
    """
    Generate a random secret key as a string suitable for configuration
    files. Size is secret key size in bytes.
    """
    if size not in SECRET_SIZES:
        raise ValueError(
            'Secret size should be one of %s' % repr(SECRET_SIZES)
        )
    return text_(base64.urlsafe_b64encode(os.urandom(size)))


def factory_args_from_settings(settings, maybe_dotted,
                               prefix='session.'):
    """
    Convert configuration (ini) file settings to a defaults-applied dict
    suitable as :func:`.get_session_factory` function arguments. 
    Only validates secret key and model class settings - 
    full validation happens inside the :func:`.get_session_factory` function.

    Arguments:
    
    settings
        dictionary of Pyramid app settings (**required**)
    maybe_dotted
        a function to resolve dotted Python name to a full class
        (**required**)
    prefix
        settings names prefix
        
    Returns dictionary of settings, suitable as args for the 
    :func:`.get_session_factory` function.
    
    Raises :exc:`.ConfigurationError` if secret_key or model_class 
    settings are invalid
    """
    s = {}
    # Process prefixed settings to prepare settings without prefix and with
    # defaults applied.
    for name, default in get_config_defaults().items():
        s[name] = settings.get(prefix + name, default)
    # Check required settings.
    for name in {'secret_key', 'model_class'}:
        if prefix + name not in settings:
            raise ConfigurationError('Required setting is missing: %s' % name)
    secret_key = settings.get(prefix + 'secret_key')
    model_class = settings.get(prefix + 'model_class')
    # Prepare serializer
    try:
        secret_bytes = base64.urlsafe_b64decode(bytes_(secret_key))
        s['serializer'] = AESGCMBytestore(secret=secret_bytes)
    except (ValueError, TypeError):
        func_name = 'pyramid_sqlalchemy_sessions.config.generate_secret_key'
        raise ConfigurationError(
            "Invalid secret key. Use %s function to generate the key, or,"
            " alternatively, you could simply copy-paste the following key "
            " into your ini file (or another configuration source):\n %s"
            % (func_name, generate_secret_key())
        )
    # Validate and prepare model class.
    try:
        cls = maybe_dotted(model_class)
        mapper = inspect(cls)
        if not isinstance(mapper, Mapper):
            raise ValueError
    except (ValueError, ImportError, NoInspectionAvailable) as e:
        raise ConfigurationError(
            "model_class setting should contain ORM class object or a"
            " dotted Python name referencing the class."
        ) from e
    s['model_class'] = cls
    return s


def _validate_config_settings(settings):
    """
    Validate runtime-configurable settings separately to reuse same
    validation logic at startup and at runtime.
    """
    single_validators = {
        'cookie_max_age': _validate_int_none,
        'cookie_path': _validate_cookie_path,
        'cookie_domain': _validate_cookie_domain,
        'cookie_secure': _validate_asbool,
        'cookie_httponly': _validate_asbool,
        'idle_timeout': _validate_int_none,
        'absolute_timeout': _validate_int_none,
        'extension_delay': _validate_smallint_none,
        'extension_deadline': _validate_positive_smallint,
        'extension_chance': _validate_nonzero_percent,
        'renewal_timeout': _validate_int_none,
        'renewal_try_every': _validate_positive_smallint,
    }
    group_validators = {
        ('absolute_timeout', 'idle_timeout'): _validate_gt,
        ('idle_timeout', 'extension_delay'): _validate_gt,
        ('idle_timeout', 'extension_delay', 'extension_chance',
         'extension_deadline'): _validate_prob_extension,
    }
    validated = {}
    s = settings
    for name, validator in single_validators.items():
        validated[name] = validator(name, s[name])
    for arg_names, group_validator in group_validators.items():
            arg_values = []
            for arg_name in arg_names:
                arg_values.append(validated[arg_name])
            group_validator(arg_names, arg_values)
    assert set(validated.keys()) == set(RUNTIME_SETTINGS)
    return validated


def _process_factory_args(args):
    """
    Process factory args: validate and create new settings if needed.
    Patch non-config mixins to pass timeout settings.
    """
    s = args

    try:
        s['dbsession_name'] = _validate_python_id(
            'dbsession_name',
            s['dbsession_name'],
        )
        s['cookie_name'] = _validate_rfc2616_token(
            'cookie_name',
            s['cookie_name'],
        )
        validated = _validate_config_settings(s)
        s.update(validated)
    except ValueError as e:
        raise ConfigurationError(e)

    cls = s['model_class']

    if not issubclass(cls, BaseMixin):
        raise ConfigurationError(
            "Model should inherit from BaseMixin for the session to work."
        )

    s['enable_userid'] = issubclass(cls, UseridMixin)
    s['enable_csrf'] = issubclass(cls, CSRFMixin)
    s['enable_configcookie'] = issubclass(cls, ConfigCookieMixin)

    # Make sure model mixin configuration is compatible with enabled timeout
    # features.
    mixin_checks = (
        (RenewalMixin, ConfigRenewalMixin, 'config_renewal',
         'renewal_timeout'),
        (IdleMixin, ConfigIdleMixin, 'config_idle', 'idle_timeout'),
        (AbsoluteMixin, ConfigAbsoluteMixin, 'config_absolute',
         'absolute_timeout')
    )
    for mixin, config_mixin, config_name, timeout in mixin_checks:
        # config_* settings have 3 possible values:
        # - None means disabled
        # - True means enabled and runtime configurable
        # - False means enabled and not runtime configurable
        if issubclass(cls, mixin):
            s[config_name] = issubclass(cls, config_mixin)
        else:
            s[config_name] = None
            if s[timeout] is not None:
                msg_template = ("%s is enabled, but the model class does not"
                                " inherit from %s")
                raise ConfigurationError(
                    msg_template % (timeout, mixin.__class__.__name__)
                )

    # Patch non-configurable mixins to help hybrid properties.
    IdleMixin.idle_timeout = s['idle_timeout']
    AbsoluteMixin.absolute_timeout = s['absolute_timeout']

    return s
