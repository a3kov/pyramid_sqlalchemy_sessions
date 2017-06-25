class ConfigurationError(Exception):
    """ Raised when the session factory has been incorrectly configured. """


class InconsistentDataError(Exception):
    """
    Raised when inconsistent session data has been found in the DB, which
    could be a sign of incorrect DB manipulations or misconfiguration.
    """


class SettingsError(Exception):
    """
    Runtime settings errors not related to incorrect settings values.
    Incorrect settings values raise :exc:`ValueError` instead.
    """


class InvalidCookieError(Exception):
    """
    Raised by serializer when session cookie is invalid prior to 
    decryption/deserializing.
    Could be a sign of a system problem or user tampering with the cookie.
    
    The library will catch this exception to avoid breaking normal flow of
    the application. You can subscribe to :class:`.InvalidCookieErrorEvent` 
    event if you want to run additional procedures when it happens. 
    """


class CookieCryptoError(Exception):
    """
    Raised by serializer when session cookie can't be decrypted 
    and/or authenticated.
    Could be a sign of a system problem, user tampering with the cookie,
    or secret key mismatch.
    
    The library will catch this exception to avoid breaking normal flow of
    the application. You can subscribe to :class:`.CookieCryptoErrorEvent`
    event if you want to run additional procedures when it happens.
    """
