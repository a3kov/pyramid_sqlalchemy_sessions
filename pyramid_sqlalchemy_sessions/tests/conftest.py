import logging
import pytest
from logging.config import dictConfig


from hypothesis import settings


settings.register_profile("one_example", settings(max_examples=1))


@pytest.fixture
def minimal_context(minimal_settings):
    from .contexts import new_context
    """ Fixture to provide context for tests not using hypothesis. """
    with new_context(minimal_settings) as context:
        yield context


@pytest.fixture
def minimal_settings():
    from .model import DummySessionModel
    return {
        'model_class': DummySessionModel,
        'secret_key': "bkg8LgEDK1IEmDqLRH9K5r5veRFW0t6y5wULhzUd7-o=",
    }


def pytest_addoption(parser):
    help_text = ("Enable logging. May output potentially overwhelming amount"
                 " of information, so pick your tests carefully.")
    parser.addoption("--enable-logging", action="store_true", help=help_text)
    
    help_text2 = "Set hypothesis max_examples=1"
    parser.addoption("--one-example", action="store_true", help=help_text2)


@pytest.fixture(autouse=True, scope='session')
def apply_cmdline_opts():
    if pytest.config.getoption("--enable-logging"):
        setup_logging()


def setup_logging():
    try:
        from rainbow_logging_handler import RainbowLoggingHandler # noqa: F401
        handler_cls = 'rainbow_logging_handler.RainbowLoggingHandler'
    except ImportError:
        handler_cls = 'logging.StreamHandler'
        
    config = {
        'version': 1,
        'root': {
            'level': logging.INFO,
            'handlers': ['console'],
        },
        'loggers': {
            'sqlalchemy.engine': {
                'level': logging.INFO,
            },
            'pyramid_sqlalchemy_sessions': {
                'level': logging.DEBUG,
            },
        },
        'handlers': {
            'console': {
                'class': handler_cls,
                'stream': 'ext://sys.stdout',
                'formatter': 'default',
            },
        },
        'formatters': {
            'default':  {
                'format': ('[%(asctime)s] %(name)s %(funcName)s():%(lineno)d'
                           '\t%(message)s'),
            }
        }
    }
    dictConfig(config)
