DB maintenance
==============

At the moment the library does not have any DB migrations code. You are 
responsible for taking care of your DB schema if your model changes.

The library will delete any expired or otherwise invalid session on the
first encounter - when receiving the session cookie. However, a session 
could expire without the server encountering it again and it's a common
situation with bots as they don't care about cookies at all. To deal with 
this problem the library has DB maintenance procedure that will remove
expired sessions from the DB. It's provided in the form of 
:command:`pyramid_session_gc` commandline script.
You can run it as the following:

``pyramid_session_gc <config_uri>``  

The script will load config provided by ``config_uri`` argument and use it's
settings to access the DB.

You can run it as often as you want using a scheduler of your choice.

.. note::
  Special care must be taken when switching global settings on and off 
  without removing existing session rows - it's developer's duty to 
  process the data so that the library code is not confused.
  It's recommended to delete existing sessions if possible,
  when changing global settings, unless you *really* know what you are doing.

