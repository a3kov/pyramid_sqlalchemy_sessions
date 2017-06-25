import pytest

from hypothesis import given, assume

from ..strategies import (
    invalid_factory_args,
    invalid_ini_settings,
    shared_config,
    shared_prefix,
    valid_ini_settings,
    valid_settings,
)


@pytest.fixture
def maybe_dotted():
    from pyramid.util import DottedNameResolver
    resolver = DottedNameResolver()
    return resolver.maybe_resolve


def test_defaults_exist():
    from pyramid_sqlalchemy_sessions.config import get_config_defaults
    settings = get_config_defaults()
    defaults_names = {
        'dbsession_name',
        'cookie_name',
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
    }
    assert set(settings.keys()) == defaults_names


def test_generate_secret_key():
    import base64
    from pyramid.compat import bytes_
    from ...config import (
        generate_secret_key,
        SECRET_SIZES,
        )    
    for size in SECRET_SIZES:
        secret = generate_secret_key(size)
        assert isinstance(secret, str)
        decoded = base64.urlsafe_b64decode(bytes_(secret))
        assert len(decoded) == size
    invalid_sizes = (0, 1, 64, None)
    for size in invalid_sizes:
        with pytest.raises(ValueError):
            secret = generate_secret_key(size)


@given(prefix=shared_prefix(), settings=valid_ini_settings())
def test_valid_ini_to_arg_success(maybe_dotted, prefix, settings):
    from ...config import (
        factory_args_from_settings,
        get_config_defaults
        )
    from sqlalchemy import inspect
    from sqlalchemy.orm.mapper import Mapper

    # Check that we properly process valid settings.
    args = factory_args_from_settings(settings, maybe_dotted, prefix)
    default_key_set = set(get_config_defaults().keys())
    assert set(args.keys()) == default_key_set | {'model_class', 'serializer'}
    mapper = inspect(args['model_class'])
    assert isinstance(mapper, Mapper)
    for attr in ('loads', 'dumps'):
        assert hasattr(args['serializer'], attr)


@given(prefix=shared_prefix(), settings=invalid_ini_settings())
def test_invalid_ini_to_arg_failure(maybe_dotted, prefix, settings): 
    from ...exceptions import ConfigurationError
    from ...config import factory_args_from_settings
    with pytest.raises(ConfigurationError):
        factory_args_from_settings(settings, maybe_dotted, prefix)


@given(args=valid_settings(), shared=shared_config())
def test_valid_args_success(args, shared):
    from ...config import _process_factory_args
    s = _process_factory_args(args)
    # Check that resulted settings match the initial generated settings we
    # used to combine the mixins.
    for name, value in shared.items():
        assert s[name] == value


@given(args=invalid_factory_args())
def test_invalid_args_failure(args):
    from ...exceptions import ConfigurationError
    from ...config import _process_factory_args
    with pytest.raises(ConfigurationError):
        s = _process_factory_args(args)
