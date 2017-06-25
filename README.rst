``pyramid_sqlalchemy_sessions`` is a
`Pyramid framework <https://docs.pylonsproject.org/projects/pyramid/>`_
add-on library providing a session implementation using 
`SQLAlchemy <http://www.sqlalchemy.org/>`_ as a storage backend.

Session data is stored in the database and is fully transactional.
Session cookie only contains randomly generated session ID required to 
refer the DB entry and is fully encrypted in AES-GCM mode using
`PyCryptodome <https://www.pycryptodome.org>`_ library.

The library features are fully structured, and you are only paying for what
you are using.

The library aims to provide secure solution by default, and to use best
security practices.

Library source code is available under MIT License.

Documentation is provided under Creative Commons Attribution-ShareAlike 4.0 
International Public License
