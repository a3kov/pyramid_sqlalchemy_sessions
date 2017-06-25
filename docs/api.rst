API Reference
=============

.. note:: All library API is importable from the root level.

Configuration
-------------

.. autofunction::
  pyramid_sqlalchemy_sessions.config.factory_args_from_settings

.. autofunction:: pyramid_sqlalchemy_sessions.config.generate_secret_key

.. autofunction:: pyramid_sqlalchemy_sessions.session.get_session_factory

.. autoclass::
  pyramid_sqlalchemy_sessions.authn.UserSessionAuthenticationPolicy

.. _mixins:

SQL Alchemy ORM Classes (Mixins)
--------------------------------

.. automodule:: pyramid_sqlalchemy_sessions.model
    :members: BaseMixin, FullyFeaturedSession, UseridMixin, CSRFMixin,
      IdleMixin, AbsoluteMixin, RenewalMixin, ConfigCookieMixin,
      ConfigIdleMixin, ConfigAbsoluteMixin, ConfigRenewalMixin


.. _events:

Events
------

.. autoclass:: pyramid_sqlalchemy_sessions.events.InvalidCookieErrorEvent

.. autoclass:: pyramid_sqlalchemy_sessions.events.CookieCryptoErrorEvent

.. autoclass:: pyramid_sqlalchemy_sessions.events.RenewalViolationEvent


.. _exceptions:

Exceptions
----------

.. automodule:: pyramid_sqlalchemy_sessions.exceptions
    :members:

