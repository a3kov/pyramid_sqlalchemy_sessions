class SessionEvent:
    """ Base session event. """
    def __init__(self, request, exception=None):
        self.request = request
        self.exception = exception


class InvalidCookieErrorEvent(SessionEvent):
    """ Pyramid :term:`event`. Fired when InvalidCookieError is catched """


class CookieCryptoErrorEvent(SessionEvent):
    """ Pyramid :term:`event`. Fired when CookieCryptoError is catched """


class RenewalViolationEvent(SessionEvent):
    """
    Pyramid :term:`event`.
    Fired when received cookie contains invalid renewal id, which could
    be a sign of a stolen session cookie or abnormal browser behavior such
    as using old cookies restored from a backup.
    """
