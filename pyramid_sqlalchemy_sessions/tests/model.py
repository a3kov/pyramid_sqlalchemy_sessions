from sqlalchemy.ext.declarative import declarative_base

from ..model import BaseMixin


Base = declarative_base()


class DummySessionModel(BaseMixin, Base):
    __tablename__ = 'test_session'


class FailingSessionModel:
    pass
