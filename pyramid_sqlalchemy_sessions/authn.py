from zope.interface import implementer

from pyramid.authentication import CallbackAuthenticationPolicy
from pyramid.interfaces import IAuthenticationPolicy


@implementer(IAuthenticationPolicy)
class UserSessionAuthenticationPolicy(CallbackAuthenticationPolicy):
    """
    Authentication policy storing user ID in the :term:`session`.
    Similar to :class:`pyramid.authentication.SessionAuthenticationPolicy`,
    with some differences:

    * uses explicit :ref:`userid-feature` feature and will only work with
      session storage implementation from the ``pyramid_sqlalchemy_sessions``
      package
    * doesn't need a prefix argument, as the ID is stored explicitly in a
      dedicated DB column
    
    """

    def __init__(self, callback=None, debug=False):
        self.callback = callback
        self.debug = debug

    def remember(self, request, userid, **kw):
        """ Store a userid in the session. """
        request.session.userid = userid
        return []

    def forget(self, request):
        """ Remove the stored userid from the session. """
        request.session.userid = None
        return []

    def unauthenticated_userid(self, request):
        """ Get userid from the session, if any. """
        return request.session.userid
