.. image:: https://readthedocs.org/projects/pyramid-sqlalchemy-sessions/badge/?version=latest
  :target: http://pyramid-sqlalchemy-sessions.readthedocs.io/en/latest/?badge=latest
  :alt: Documentation Status

``pyramid_sqlalchemy_sessions`` is a
`Pyramid framework <https://docs.pylonsproject.org/projects/pyramid/>`_
add-on library providing a session implementation using 
`SQLAlchemy <http://www.sqlalchemy.org/>`_ as a storage backend.

Session data is stored in the database and is fully transactional.
Session cookie only contains randomly generated session ID required to 
refer the DB entry and is fully encrypted in AES-GCM mode using
`PyCryptodome <https://www.pycryptodome.org>`_ library.


Library
`source code <https://github.com/corehack/pyramid_sqlalchemy_sessions>`_
is available under MIT License.

`Documentation <https://pyramid-sqlalchemy-sessions.readthedocs.io/>`_
is provided under 
`Creative Commons Attribution-ShareAlike 4.0 International Public License <\
https://creativecommons.org/licenses/by-sa/4.0/legalcode>`_


