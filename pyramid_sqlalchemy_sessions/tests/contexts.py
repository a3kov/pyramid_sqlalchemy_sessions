import time
import transaction
import zope.sqlalchemy

from pyramid.decorator import reify
from pyramid.testing import (
    DummyRequest,
    setUp,
    tearDown,
)
from pyramid.util import DottedNameResolver
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..config import factory_args_from_settings
from ..session import get_session_factory


class new_context():
    """ Manager to provide new test context for each test example. """
    def __init__(
        self,
        settings,
        set_time=None,
        isolation_level=None
    ):
        import pyramid_sqlalchemy_sessions.session as session_module
        self._sm = session_module
        url = 'sqlite://'
        kwargs = {}
        if isolation_level is not None:
            kwargs['isolation_level'] = isolation_level
        self.engine = create_engine(url, **kwargs)
        self.settings = settings
        self.metadata = settings['model_class'].metadata
        if set_time is None:
            set_time = int(time.time())
        self.time = set_time
        self._cookies = {}
        self.vary = None

    def __enter__(self):
        # Configurator expects raw ini settings.
        prefixed = {'session.' + k: v for k, v in self.settings.items()}
        self.config = setUp(settings=prefixed)
        self.metadata.create_all(self.engine)
        self._int_now = self._sm.__dict__['int_now']
        self._sm.__dict__['int_now'] = lambda: self.time
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._sm.__dict__['int_now'] = self._int_now
        self.metadata.drop_all(self.engine)
        tearDown()

    @property
    def cookies(self):
        self._cookies = {
            k: v for k, v in self._cookies.items()
            if v[1] is None or v[1] > self.time
        }
        return {k[0]: v[0] for k, v in self._cookies.items()}

    def set_cookie(self, name, path, domain, value, max_age, secure, httponly):
        if max_age is None:
            expire = None
        else:
            expire = self.time + max_age 
        self._cookies[(name, path, domain)] = (
            value, expire, secure, httponly
        )

    def delete_cookie(self, name, path, domain):
        del self._cookies[(name, path, domain)]


class new_request(DummyRequest):
    def __init__(self, context=None, **kw):
        super().__init__(**kw)
        if context is not None:
            context.vary = None  # Cleanup.
            self.context = context
            self.cookies = context.cookies
            self.registry = context.config.registry

    def __enter__(self):
        self.tm.begin()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_value is not None:
            self.tm.abort()
        else:
            self.tm.commit()
        self._process_response_callbacks(self.context)

    @property
    def session(self):
        if getattr(self, '_session', None) is None:
            args = factory_args_from_settings(
                self.context.settings,
                DottedNameResolver().maybe_resolve,
                '',
            )
            factory = get_session_factory(**args)
            self._session = factory(self)
        return self._session

    @session.setter
    def session(self, v):
        pass

    @reify
    def dbsession(self):
        factory = sessionmaker()
        factory.configure(bind=self.context.engine)
        dbsession = factory()
        zope.sqlalchemy.register(dbsession, transaction_manager=self.tm)
        return dbsession

    @reify
    def tm(self):
        return transaction.TransactionManager(explicit=True)
