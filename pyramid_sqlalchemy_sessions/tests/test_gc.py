import pytest

from hypothesis import (
    assume,
    given,
)
import hypothesis.strategies as st

from .contexts import (
    new_context,
    new_request,
)
from .strategies import (
    shared_config,
    valid_settings,
)


@pytest.fixture
def request(minimal_context):
    return new_request(minimal_context)


@pytest.fixture
def patch_bootstrap(monkeypatch, request):
    bootstrap = DummyBootstrap(
        request=request,
        registry=request.context,
    )
    monkeypatch.setattr(
        'pyramid_sqlalchemy_sessions.gc.bootstrap',
        bootstrap
    )


class DummyBootstrap(object):
    def __init__(self, registry, request):
        self.registry = registry
        self.request = request

    def __call__(self, *a, **kw):
        return DummyAppEnvironment(
            registry=self.registry,
            request=self.request,
        )


class DummyAppEnvironment(dict):
    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass


class DummyLogger():
    msg = None
    def info(self, msg):
        self.msg = msg


def test_main():
    from ..gc import main
    assert main(['pyramid_session_gc']) == 2


def test_GCCommand_parse_config(minimal_context, request, patch_bootstrap):
    from ..gc import GCCommand
    args = GCCommand.parse_config('foo', '')
    args_cls = args['settings']['model_class']
    context_cls = minimal_context.settings['model_class']
    assert args_cls == context_cls
    assert args['dbsession'] == request.dbsession
    assert args['tm'] == request.tm


def test_GCCommand_runs_Cleaner(
    monkeypatch,
    minimal_context,
    request,
    patch_bootstrap,
    ):
    from ..gc import GCCommand
    cleaner_args = {}
    class DummyCleaner():
        def __init__(self, settings, dbsession, tm):
            self.dbsession = dbsession
            self.settings = settings
            self.tm = tm

        def clean(self):
            nonlocal cleaner_args
            cleaner_args = {
                'dbsession': self.dbsession,
                'settings': self.settings,
                'tm': self.tm,
            }
    monkeypatch.setattr(
        'pyramid_sqlalchemy_sessions.gc.Cleaner',
        DummyCleaner
    )

    logging_config_uri = ''
    def setup_logging(config_uri):
        nonlocal logging_config_uri
        logging_config_uri = config_uri
    monkeypatch.setattr(
        'pyramid_sqlalchemy_sessions.gc.setup_logging',
        setup_logging
    )
    command = GCCommand(['pyramid_session_gc', 'foobar_config'], '')
    assert command.run() == 0
    assert logging_config_uri == 'foobar_config'
    assert cleaner_args['dbsession'] == request.dbsession
    assert cleaner_args['tm'] == request.tm
    cleaner_cls = cleaner_args['settings']['model_class']
    settings_cls = minimal_context.settings['model_class']
    assert cleaner_cls == settings_cls


@given(settings=valid_settings(), shared=shared_config())
def test_Cleaner(monkeypatch, settings, shared):
    cls = settings['model_class']

    def create_session(context, session_cols=None):
        context._cookies = {}
        with new_request(context) as request:
            request.session['test'] = 1
            id = request.session._session.id
        if session_cols:
            with new_request(context) as request:
                s = request.dbsession.query(cls).get(id)
                for k, v in session_cols.items():
                    setattr(s, k, v)
        return id

    def session_exists(id, context):
        with new_request(context) as request:
            return request.dbsession.query(cls).get(id) != None

    def clean(context, shared):
        from ..gc import Cleaner
        monkeypatch.setattr(
            'pyramid_sqlalchemy_sessions.gc.int_now',
            lambda: context.time
        )
        request = new_request(context)
        settings = context.settings.copy()
        settings.update(shared)
        cleaner = Cleaner(request.dbsession, settings, request.tm)
        cleaner.logger = DummyLogger()
        cleaner.clean()
        assert cleaner.logger.msg is not None

    config_idle =  shared['config_idle']
    config_absolute = shared['config_absolute']
    idle_timeout = settings['idle_timeout']
    absolute_timeout = settings['absolute_timeout']

    # Simplest cases: timeouts disabled (both runtime-configurable and not).
    if idle_timeout is None and absolute_timeout is None:
        with new_context(settings) as context:
            id = create_session(context)
            clean(context, shared)
            assert session_exists(id, context)
        return

    with new_context(settings) as context:
        # Prepare test sessions        
        if idle_timeout:
            # Here we don't care about absolute timeout simply
            # because idle < absolute
            idle_expiring_id = create_session(context)
            if config_idle:
                # and idle_id will reach absolute timeout, if any.
                idle_id = create_session(
                    context,
                    {'idle_timeout': None, 'idle_expire': None}
                )
        if absolute_timeout:
            absolute_expire = context.time + absolute_timeout
            # Here idle timeout could interfere, so simulate idle extension
            # beyond abs.timeout, if needed.
            if idle_timeout:
                session_cols = {'idle_expire': absolute_expire + 10}
            else:
                session_cols = {}
            absolute_expiring_id = create_session(context, session_cols)
            if config_absolute:
                session_cols.update(
                    {'absolute_timeout': None, 'absolute_expire': None}
                )
                absolute_id = create_session(context, session_cols)

        # Check idle expiration
        if idle_timeout:
            # Before idle timeout.
            context.time += idle_timeout - 1
            clean(context, shared)
            assert session_exists(idle_expiring_id, context)
            if config_idle:
                assert session_exists(idle_id, context)
            if absolute_timeout:
                assert session_exists(absolute_expiring_id, context)
                if config_absolute:
                    assert session_exists(absolute_id, context)
            # After idle timeout.
            context.time += 2
            clean(context, shared)
            assert not session_exists(idle_expiring_id, context)
            if config_idle:
                assert session_exists(idle_id, context)
            if absolute_timeout:
                assert session_exists(absolute_expiring_id, context)
                if config_absolute:
                    assert session_exists(absolute_id, context)

        # Check absolute expiration.
        if absolute_timeout:
            # Before abs. timeout
            context.time = absolute_expire - 1
            assert session_exists(absolute_expiring_id, context)
            if config_absolute:
                assert session_exists(absolute_id, context)
            if idle_timeout and config_idle:
                assert session_exists(idle_id, context)
            # After abs. timeout    
            context.time += 2
            clean(context, shared)
            assert not session_exists(absolute_expiring_id, context)
            if idle_timeout and config_idle:
                assert not session_exists(idle_id, context)
            if config_absolute:
                assert session_exists(absolute_id, context)

    # Automatic undo is per test only, not per example. 
    monkeypatch.undo()
