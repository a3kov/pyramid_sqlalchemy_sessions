import json
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    LargeBinary,
    PickleType,
    SmallInteger,
    Unicode,
)
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.types import (
    JSON,
    TypeDecorator,
)


class UUID(TypeDecorator):
    """ UUID type, native for PostgreSQL or LargeBinary(16) for other DBs. """
    impl = LargeBinary

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(pgUUID())
        else:
            return dialect.type_descriptor(LargeBinary(16))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            return value.bytes

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return uuid.UUID(value)
        else:
            return uuid.UUID(bytes=value)


class JSONText(TypeDecorator):
    """ JSON type using unicode text columns to store JSON-encoded data."""
    impl = Unicode

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class BaseMixin:
    """
    Base session ORM class mixin. Subclass this mixin to get a minimal
    working session without any extra features.
    """
    id = Column(UUID, primary_key=True)
    created = Column(Integer, nullable=False)

    @declared_attr
    def data(cls):
        return Column(MutableDict.as_mutable(PickleType))

    @declared_attr
    def flash(cls):
        return Column(MutableDict.as_mutable(
            JSON().with_variant(JSONText, 'sqlite')
        ))


class UseridMixin:
    """ Mixin that enables :ref:`userid-feature` feature. """
    userid = Column(Integer)


CSRF_TOKEN_SIZE = 20


class CSRFMixin:
    """ Mixin that enables :ref:`csrf-feature` feature. """
    csrf_token = Column(LargeBinary(CSRF_TOKEN_SIZE))


class RenewalMixin:
    """ Mixin that enables :ref:`renewal-timeout-feature` feature. """
    renewal_id = Column(UUID)
    renewed = Column(Integer, nullable=False)
    renewal_tried = Column(Integer, nullable=False)
    renewal_next = Column(UUID)


class IdleMixin:
    """ Mixin that enables :ref:`idle-timeout-feature` feature. """
    idle_expire = Column(Integer)


class AbsoluteMixin:
    """ Mixin that enables :ref:`absolute-timeout-feature` feature. """
    # Since we always provide "created" timestamp to satisfy the ISession
    # requirement, and the timeout is same for all sessions, it's enough to
    # calculate absolute_expire using created column.
    @hybrid_property
    def absolute_expire(self):
        if self.absolute_timeout is not None:
            # Note: self.absolute_timeout should be monkeypatched.
            return self.created + self.absolute_timeout

    @absolute_expire.setter
    def absolute_expire(self, value):
        raise NotImplementedError(
            "For sessions with non-configurable absolute timeout, you change"
            " expiration by changing the global absolute_timeout setting."
        )


class ConfigCookieMixin:
    """ Mixin that enables :ref:`config-cookie-feature` feature. """
    cookie_max_age = Column(Integer)
    cookie_path = Column(Unicode(255), nullable=False)
    cookie_domain = Column(Unicode(255))
    cookie_secure = Column(Boolean, nullable=False)
    cookie_httponly = Column(Boolean, nullable=False)


class ConfigIdleMixin(IdleMixin):
    """ Mixin that enables :ref:`config-idle-timeout-feature` feature. """
    idle_timeout = Column(Integer)
    extension_delay = Column(SmallInteger)
    extension_chance = Column(SmallInteger, nullable=False)
    extension_deadline = Column(SmallInteger, nullable=False)


class ConfigAbsoluteMixin(AbsoluteMixin):
    """ Mixin that enables :ref:`config-absolute-timeout-feature` feature. """
    absolute_expire = Column(Integer)

    # We need to store expiration timestamp for indexing, so having a separate
    # timeout column would only bring a source of inconsistency errors.
    @hybrid_property
    def absolute_timeout(self):
        if self.absolute_expire is not None:
            return self.absolute_expire - self.created

    @absolute_timeout.setter
    def absolute_timeout(self, value):
        if value is not None:
            self.absolute_expire = self.created + value
        else:
            self.absolute_expire = None


class ConfigRenewalMixin(RenewalMixin):
    """ Mixin that enables :ref:`config-renewal-timeout-feature` feature. """
    renewal_timeout = Column(Integer)
    renewal_try_every = Column(SmallInteger, nullable=False)


class FullyFeaturedSession(
    UseridMixin,
    CSRFMixin,
    ConfigCookieMixin,
    ConfigIdleMixin,
    ConfigAbsoluteMixin,
    ConfigRenewalMixin,
    BaseMixin,
):
    """
    Class providing all features of all mixins together. Use it if you
    are really using all features, or if you don't care about running dead
    code or having unused columns in the DB.
    """
