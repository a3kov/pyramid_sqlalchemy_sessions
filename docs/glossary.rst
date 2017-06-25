Glossary of terms
=================

.. glossary::

  session      
      In the context of web applications, a temporary storage of information
      related to the current user. In the Pyramid framework it's usually an
      object implementing ``pyramid.interfaces.ISession``

  session factory
      A callable returning :term:`session` object. In the Pyramid framework
      it's usually an object implementing
      ``pyramid.interfaces.ISessionFactory``

  serializer
      An object with ``dumps`` and ``loads`` methods, packing and unpacking
      data to/from a cookie value.
  
  model
      SQLAlchemy ORM model class, subclassing *declarative Base* and selected 
      session model mixins. In the context of this library, a model is a
      class referenced by the ``model_class`` setting.
  
  new session
      Session is new when it hasn't been saved (i.e. committed) to the 
      database yet. You can get a new session when you start it, or after
      you invalidate a session.
  
  session data
      The main purpose of session is to store useful data. Examples of 
      such data in the library include:
      
      * any session dict values
      * flash messages
      * user ID with :ref:`userid-feature` feature enabled
      * CSRF token with :ref:`csrf-feature` feature enabled
      * any internal data the libary may need to save (not exposed to the 
        developer)
      
      .. note:: Session settings are metadata, not the data.
      
  lazy session
      Session is called lazy if it is not saved without any data.
      The library session is lazy: you need to store :term:`session data`
      to make it :term:`dirty <dirty session>` and to save it in the database. 
  
  clean session
      Session not containing any :term:`session data`.
  
  dirty session
      Session having unsaved (uncommitted) :term:`session data`.
  
  session extension
      A process of updating session idle expiration timestamp, or in 
      other words, applying idle timeout using the current time as a base.
      Happens once per request.

  session renewal
      A procedure that includes rotating a separate randomly generated 
      renewal ID, described in detail in :ref:`renewal-timeout-feature`      
      
      