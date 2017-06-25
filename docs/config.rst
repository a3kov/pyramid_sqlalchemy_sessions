===================
Configuration guide
===================


Introduction 
============
You can configure session factory in 2 steps:

#. Pick desired :doc:`session features <features>` and add corresponding 
   :ref:`mixins` to the bases list of your :term:`model`.
   
   The library will detect mixin combination and enable corresponding 
   session features.
   
   .. note:: It's much better to exclude mixins of features that you are 
             not planning to use:
             
             * your database will save some resources
             * the library will run a bit less code
             * if you accidentally try to enable a timeout setting that
               depends on a missing mixin, you will get explicit error
               at startup instead of a runtime error.
  
#. Apply session settings - globally, or per-session (if the setting is 
   configurable at runtime). Global settings are provided at startup, and
   per-session settings use global settings as defaults. In case global
   settings are not provided, library defaults will be used as globals.
   (see :ref:`settings`)

.. note::
  Timeout-related features have settings also deciding if the feature is 
  enabled or not:

  * ``idle_timeout``
  * ``absolute_timeout``
  * ``renewal_timeout``

  For these features, even if corresponding mixin is included, the feature will
  not work when the setting value is ``None``.

  
Model configuration
===================
In the following example we configure a session storing user ID, having
non-runtime-configurable Absolute Timeout and runtime-configurable
Idle Timeout. The example also showcases:

* ability to customize model columns - we use UUID as User ID instead 
  of the default integer.
* eager-loading of the user object.

::
  
  from sqlalchemy import (
    Column,
    ForeignKey,
  )
  from sqlalchemy.dialects.postgresql import UUID
  from sqlalchemy.orm import relationship
  from pyramid_sqlalchemy_sessions import (
      BaseMixin,
      UseridMixin,
      AbsoluteMixin,
      ConfigIdleMixin,
  )
  # Using default declarative Base provided by the cookiecutter.
  from .meta import Base
  
  class Session(
      UseridMixin,
      AbsoluteMixin,
      ConfigIdleMixin,
      BaseMixin,
      Base,
      ):
      __tablename__ = 'session'
      
      userid = Column(UUID(as_uuid=True), ForeignKey('user.id'))
      # user instance loaded automatically when user is logged in.
      user = relationship('User', backref='sessions', lazy='joined')


.. note::
  Runtime-configurable features mixins subclass their non-configurable
  versions, so you don't need to include both.

.. note::
  Don't forget to add DB indexes to your session table! The library doesn't
  provide one, as it's difficult to create universal index solution for all
  mixin configurations and different DB engines.
  

.. _working-with-settings:

Working with settings 
=====================
Some settings only meant to be set once and forgotten, such as
``cookie_name`` or ``dbsession_name``.
But most other settings are accessable and even configurable at runtime 
(if the corresponding session model mixin is enabled). 

You can access current session settings using the settings object::

  # Read
  idle_timeout = request.session.settings.idle_timeout
  # Settings is also a dict-like object.
  absolute_timeout = request.session.settings['absolute_timeout']

By default you can only read the settings. But when you enable a 
runtime-configurable feature, it's settings can be changed also: ::

  # Suppose configurable cookie settings feature is enabled.
  # You need to put settings in editable mode first.
  request.session.settings.edit()
  request.session.settings.cookie_max_age = 12345
  # When you are done, you need to save it.
  # Settings are always validated before saving.
  request.session.settings.save()
  # You can use settings as context manager so that edit and save 
  # is called automatically
  with request.session.settings as s:
      s['cookie_max_age'] = 54321

.. note::
  Currently changing of settings works only for a :term:`new session`,
  otherwise you will get a :exc:`.SettingsError` exception.

.. note::
  The session implementation provided by the library is 
  :term:`lazy <lazy session>`, and will not persist :term:`clean session`,
  so any changes of settings for such sessions also won't be persisted
  in the DB.


.. _settings:

Configuration settings reference
================================

.. _required-settings:

Required settings
-----------------

secret_key : str
    This setting is required by default :term:`serializer` when the library
    :func:`includeme` function runs.
    
    Not meant to be accessible at runtime.

serializer : object
    Controls what :term:`serializer` to use. Only needed if you want to 
    configure :term:`session factory` manually and to skip the
    :func:`includeme`.
    
    Not meant to be accessible at runtime.
    

model_class : class
    Controls what :term:`model` to use to store session data in the DB. Should
    be a dotted Python name referencing the class (if provided by default
    way of configuration, e.g. through the ini file) or the class object 
    itself (may need to use this option if you are configuring the session 
    factory manually).
    
    Not meant to be accessible at runtime.


.. _optional-settings:

Optional settings (settings with library defaults)
--------------------------------------------------

dbsession_name : str
    Session code will try to access :term:`SQLAlchemy session<sqla:session>`
    as an attribute of :term:`request` using this name.
    
    Not meant to be accessible at runtime.
    
    Default: ``dbsession``
    
cookie_name : str
    Name of the session cookie (will appear in ``Cookie`` and ``Set-Cookie`` 
    headers).
    See :doc:`webob:index` and :rfc:`6265` for details.
    
    Not meant to be accessible at runtime.
    
    Default: ``session``

cookie_max_age : int or None
    How long the browser will store the cookie. ``None`` is for
    non-persistent cookie.
    See :doc:`webob:index` and :rfc:`6265` for details.
    
    Default: ``None``

cookie_path : str
    Path of the session cookie. Can be a valid path only
    (starting with ``/``).
    See :doc:`webob:index` and :rfc:`6265` for details.
    
    Default: ``/``

cookie_domain : str or None
    Domain of the session cookie.
    See :doc:`webob:index` and :rfc:`6265` for details.
    
    Default: ``None``
    
cookie_secure : bool
    Boolean flag instructing the browser to send cookie in HTTPS mode only.
    See :doc:`webob:index` and :rfc:`6265` for details.
    
    Default: ``False``

cookie_httponly : bool
    Boolean flag instructing the browser to prevent scripts accessing 
    the cookie.
    See :doc:`webob:index` and :rfc:`6265` for details.
    
    Default: ``True``

idle_timeout : int or None
    Controls idle timeout value.
    See :ref:`idle-timeout-feature` for detailed explanation.
    
    Default: ``None`` 

absolute_timeout : int or None
    Controls absolute timeout value.
    See :ref:`absolute-timeout-feature` for detailed explanation.
    
    Default: ``None``

renewal_timeout : int or None
    Controls renewal timeout value.
    See :ref:`renewal-timeout-feature` for detailed explanation.
    
    Default: ``None``
    
renewal_try_every : int
    When :ref:`renewal-timeout-feature` feature is working, the library will
    try to *renew* the session every ``renewal_try_every`` seconds until
    success.
    See :ref:`renewal-timeout-feature` for detailed explanation.
    
    Default: 5

extension_delay : int or None
    When :ref:`idle-timeout-feature` feature is working, the library will
    not try hard to extend the session more often than every
    ``extension_delay`` seconds.
    See :ref:`idle-timeout-feature` for detailed explanation.
    
    Default: ``None``

extension_chance : int
    When :ref:`idle-timeout-feature` feature is working, the library will
    *extend* the session randomly, using ``extension_chance`` chance
    (in percents).
    See :ref:`idle-timeout-feature` for detailed explanation.
    
    Default: 100

extension_deadline : int
    When :ref:`idle-timeout-feature` feature is working, and 
    ``extension_chance < 100`` the library will *extend* the session after
    reaching the ``extension_deadline`` timeout, as if ``extension_chance``
    was 100.
    See :ref:`idle-timeout-feature` for detailed explanation.
    
    Default: 1
