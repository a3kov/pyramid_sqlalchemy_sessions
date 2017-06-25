import pytest


@pytest.fixture
def request():
    from pyramid.testing import DummyRequest
    class DummySession:
        userid = None
    return DummyRequest(session=DummySession())


@pytest.fixture
def policy_cls():
    from ..authn import UserSessionAuthenticationPolicy
    return UserSessionAuthenticationPolicy


@pytest.fixture
def policy(policy_cls):
    return policy_cls()


def test_implements_IAuthenticationPolicy(policy_cls):
    from zope.interface.verify import (
        verifyClass,
        verifyObject,
    )
    from pyramid.interfaces import IAuthenticationPolicy
    verifyClass(IAuthenticationPolicy, policy_cls)
    verifyObject(IAuthenticationPolicy, policy_cls())


def test_unauthenticated_userid_returns_None(request, policy):
    assert policy.unauthenticated_userid(request) is None


def test_unauthenticated_userid(request, policy):
    request.session.userid = 123
    assert policy.unauthenticated_userid(request) == 123


def test_authenticated_userid_empty_session_userid(request, policy):
    assert policy.authenticated_userid(request) is None


def test_authenticated_userid_callback_returns_None(request, policy_cls):
    request.session.userid = 123
    def callback(userid, request):
        return None
    policy = policy_cls(callback)
    assert policy.authenticated_userid(request) is None


def test_authenticated_userid(request, policy_cls):
    request.session.userid = 123
    def callback(userid, request):
        return True
    policy = policy_cls(callback)
    assert policy.authenticated_userid(request) == 123


def test_effective_principals_empty_session_userid(request, policy):
    from pyramid.security import Everyone
    assert policy.effective_principals(request) == [Everyone]


def test_effective_principals_callback_returns_None(request, policy_cls):
    from pyramid.security import Everyone
    request.session.userid = 123
    def callback(userid, request):
        return None
    policy = policy_cls(callback)
    assert policy.effective_principals(request) == [Everyone]


def test_effective_principals(request, policy_cls):
    from pyramid.security import Everyone
    from pyramid.security import Authenticated
    request.session.userid = 123
    def callback(userid, request):
        return ['group.foo']
    policy = policy_cls(callback)
    expected = [Everyone, Authenticated, 123, 'group.foo']
    assert policy.effective_principals(request) == expected


def test_remember(request, policy):
    assert policy.remember(request, 123) == []
    assert request.session.userid == 123


def test_forget(request, policy):
    request.session.userid = 123
    assert policy.forget(request) == []
    assert request.session.userid is None


def test_forget_no_identity(request, policy):
    assert policy.forget(request) == []
    assert request.session.userid is None
