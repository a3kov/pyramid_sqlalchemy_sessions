===============
Getting Started
===============


Introduction
============

``pyramid_sqlalchemy_sessions`` is a :doc:`Pyramid framework <pyramid:index>`
add-on library providing a :term:`session` implementation using 
`SQLAlchemy <http://www.sqlalchemy.org/>`_ as a storage backend.

Session data is stored in the database and is fully transactional.
Session cookie only contains randomly generated session ID required to 
refer the DB entry and is fully encrypted in AES-GCM mode using
`PyCryptodome <https://www.pycryptodome.org>`_ library.

The library features are fully modularized, and you are only paying for what
you are using.

The library aims to provide secure solution by default, and to use best
security practices.


Why would you (not) need this library
=====================================

You may need this library if:

* You need ability to store login and session state server-side, for security
  or any other reasons
  
* You need reliable session data storage.
  As we depend on `SQLAlchemy <http://www.sqlalchemy.org/>`_, you can try to
  use any ACID-compatible DB engine if it's supported by SQLAlchemy.
  
* You want to store important data in the session.
  Valid usecases include things like: authentication data, 
  online store shopping cart, multi-step form wizard state, 
  user preferences, etc.

* You want (or don't mind) your session data to be transactional.
  The library will use same dbsession as your app and will automatically join
  all transactions. So you can be sure that any ``ROLLBACK`` for your main
  data will not leave inconsistent session data.
  

You may skip this library if:

* you prefer lightweight solutions even if it compromises security or features.
  In this case, cookie-based session backend is a better pick.

* you want to store not very important information or even throw-away data

* you require that session data should be always saved, regardless of
  transaction results, e.g. if you collect statistics.
  This is a big No to this library.

* you don't care about transactions, data reliability and don't mind to lose
  session data from time to time.
  In this case you could pick a memory-based session backend, like 
  `pyramid_redis_sessions`_. or `pyramid_session_redis`_

  .. _pyramid_redis_sessions:
    https://pypi.python.org/pypi/pyramid_redis_sessions
    
  .. pyramid_session_redis:
    https://github.com/jvanasco/pyramid_session_redis
  
.. note::
  Without a server-side backend it's impossible to securely
  terminate any session, as cookie-based solutions rely on gentleman
  agreement to "forget" the cookie, which can't be enforced.


Before you begin
================

The library will assume the following:

* You are using `SQLAlchemy <http://www.sqlalchemy.org/>`_ as a data
  storage backend. The library tries to use portable solutions as much as
  possible, but the author does not have ability to test every engine out
  there, especially proprietary ones. So for a start we can say that 
  PostgreSQL and MySQL-family (MariaDB, etc) are supported. SQLite works but
  it's main purpose is to run test cases as generally it has poor 
  support for concurrency and transactions.

* Your database and SQLALchemy ``engine`` are configured to work in 
  ``SERIALIZABLE`` transaction isolation mode. It's the best mode to avoid
  any data anomalies and if the DB implements optimistic locking such as 
  `MVCC <https://en.wikipedia.org/wiki/Multiversion_concurrency_control>`_,
  is also best for performance: avoid excessive locks but be ready to retry
  the transaction (basically what :mod:`pyramid_retry` is doing). 
  
* You are using :mod:`pyramid_tm` to manage your transactions. Transaction
  will span the whole request, without any manual commits by the developer.
  It's important as breaking this workflow could break the whole library.
  Savepoints compatibility haven't been tested yet.

* You don't clear your :term:`sqla:session` by running 
  ``dbsession.expunge_all()``, etc.
  As the library will share the DB :term:`sqla:session` with your app,
  both your main data and the library data need to coexist peacefully.
  
  .. note:: 
    It's possible to use a separate :term:`sqla:session` for the library,
    as generally the library can't distinguish *right* sessions 
    from *wrong* ones, but such configuration haven't been tested and
    is not supported at the moment.

* Since Pyramid 1.9, the library will assume you are using 
  :mod:`pyramid_retry` to retry failed transactions.
  Retrying is not required technically, but in most cases you 
  would want to retry instead of showing 500 page to the
  user, so it's a welcomed feature.
  
* You code expects that your :term:`session data` won't be always committed 
  to the DB. For example, in Pyramid you can *raise* or
  *return* HTTP exceptions. For an app the difference between the two 
  is not always significant, but for the library it is huge:
  *raising* a seemingly safe :exc:`pyramid.httpexceptions.HTTPFound`
  will always ``ROLLBACK`` the transaction, even while this type of response
  is successful. Inside :mod:`pyramid_tm` there are some tweaks for what is
  a success or not, but generally you want to avoid exceptions if you can,
  if you want your :term:`session data` to be committed at all.


Make sure your app configuration includes the following line: ::

  tm.annotate_user = False

Annotations can cause problems with the library, as it may start
a premature transaction before ``pyramid_tm`` has begun.

Also using explicit transaction manager by setting ``tm.manager_hook`` as
described in :mod:`pyramid_tm` docs is recommended.


Quick Start
===========

Let's configure a minimal session. We will assume you created a project
using cookiecutter, and your DB session is available as ``request.dbsession``.
 
Create ``session.py`` file in your ``models`` subpackage and add the 
following lines: ::

  from pyramid_sqlalchemy_sessions import BaseMixin
  # Using default declarative Base provided by the cookiecutter.
  from .meta import Base
  
  
  class Session(BaseMixin, Base):
      __tablename__ = 'session'

Import your new model in the ``__init__.py`` of your models subpackage and
initialize the db using the script generated by the cookiecutter.

Then, start a python shell and run: ::

  >>> from pyramid_sqlalchemy_sessions import generate_secret_key
  >>> generate_secret_key()

Copy the generated key (without surrounding single quotes) to clipboard.
Add the following settings to the ``[app:main]`` section of your
configuration file: ::

  session.secret_key = paste your generated key here
  session.model_class = yourproject.models.session.Session

And finally, include the library configuration in your project 
main ``__init__.py`` file: ::

  def main(global_config, **settings):
      config = Configurator(settings=settings)
      config.include('pyramid_sqlalchemy_sessions')
      config.scan()
      return config.make_wsgi_app()

Now unless you have some conflict in your configuration or you did a mistake,
the session should be working.









 
  