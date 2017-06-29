Detailed features guide
=======================

.. _isession-feature:

Basic Session Usage
-------------------

You can always use basic session features dictated by the
``pyramid.interfaces.ISession`` API:

* store pickle-serializable data in the session dict
* store and fetch flash messages


.. note:: 
  Unlike default cookie-based session implementations provided by the 
  Pyramid, the library does not store flash messages in the main session
  dict.
  So for example ``session.clear()`` will not clear the messages.


.. _idle-timeout-feature:

Idle Timeout
------------
The feature implements `OWASP "Idle Timeout" security policy 
<https://www.owasp.org/index.php/Session_Management_Cheat_Sheet\
#Idle_Timeout>`_.
With this feature enabled, user's session will expire after ``idle_timeout``
seconds has passed since his last session activity.

For this feature to work properly, every request accessing session has to
*extend* it, i.e. to update it's expiration timestamp. This is one of the
complaints related to DB-based session backends: traditional relational
databases don't like too many writes because of locking, slow discs,
replication, etc. 

At minimum, any session write (when :term:`session data` is put or changed 
inside the session) will extend it. But if the code processing the request
only reads the session, that's when we can optimize the DB performance using 
dedicated settings:

* ``extension_delay`` allows to lower the frequency of extensions, i.e. db
  writes. Session reads will not extend the session sooner than
  ``extension_delay`` since last extension.
  
* ``extension_chance`` allows to randomize the extensions by session reads.
  It's a percentage-based chance to extend: every time an extension could 
  happen (including the requirement to pass ``extension_delay`` if the 
  latter was enabled) a dice will be rolled to decide if the extension
  should happen.
  
  This setting is experimental. It's main purpose is to deal with very
  specific and not very common scenario: concurrent requests using same
  session. Concurrent writes to same rows can cause performance
  issues because of row locks and serialization conflicts.
  Note that this setting affects all requests, not only parallel ones,
  so it has to be applied very carefully (if at all).
  
* ``extension_deadline`` allows to limit the randomness of the extension,
  when ``extension_chance`` is lower than 100. Upon reaching the
  ``extension_deadline`` since last extension, next session read will
  always extend, as if ``extension_chance`` was set to 100.

The most important side effect of these 3 settings is they affect 
error margin when calculating idle timeout: sessions will be 
expired earlier than should have been. If, and to what extent it is 
acceptable is for you to decide.


.. _config-idle-timeout-feature:

Runtime-configurable Idle Timeout
---------------------------------
Same as :ref:`idle-timeout-feature`, but allows to use different feature
settings per session. See :ref:`working-with-settings` for details.


.. _absolute-timeout-feature:

Absolute Timeout
----------------
The feature implements `OWASP "Absolute Timeout" security policy 
<https://www.owasp.org/index.php/Session_Management_Cheat_Sheet\
#Absolute_Timeout>`_.
With this feature enabled, user's session will expire after
``absolute_timeout`` seconds has passed since creation of the session,
regardless of any session activity.


.. _config-absolute-timeout-feature:

Runtime-configurable Absolute Timeout
-------------------------------------
Same as :ref:`absolute-timeout-feature`, but allows to use different feature
settings per session. See :ref:`working-with-settings` for details.


.. _renewal-timeout-feature:

Renewal Timeout
---------------
The feature implements `OWASP "Renewal Timeout" security policy 
<https://www.owasp.org/index.php/Session_Management_Cheat_Sheet\
#Renewal_Timeout>`_.
With this feature enabled, user's session will periodically run *renewal*
procedure. The procedure can be described as following:

#. Generate random renewal ID in addition to the main ID on session creation
#. Wait until ``renewal_timeout`` seconds has passed since creation 
   (or last renewal).
#. Upon reaching the timeout, try to *renew* the session by generating a 
   candidate renewal ID and sending it to the user.
#. Wait until we receive acknowledgement - session cookie with the candidate
   ID. If there's no acknowledgement, try again after ``renewal_try_every``
   seconds has passed since the last renewal try. Until acknowledgement is 
   received, the old renewal ID is valid.  
#. When user sends a session cookie containing the candidate ID, delete old
   renewal ID and use the candidate instead. At this moment renewal is
   finished.
#. After this, if an old (or any otherwise unknown) renewal id is received,
   invalidate the session.
   
The purpose of the renewal is to limit the time an attacker could use 
stolen session cookie (assuming the theft happened once and the attacker 
can't access newly issued cookies).
Also this protocol allows to detect the fact of theft itself, 
when both the attacker and the user try to use the same session. We may not
know who is who, but we certainly know that there are 2 versions of the
same cookie and one of them is invalid.


.. _config-renewal-timeout-feature:

Runtime-configurable Renewal Timeout
------------------------------------
Same as :ref:`renewal-timeout-feature`, but allows to use different feature
settings per session. See :ref:`working-with-settings` for details.


.. _config-cookie-feature:

Runtime-configurable cookie settings
------------------------------------
The feature allows to use different cookie settings per session. 
See :ref:`working-with-settings` for details.


.. _userid-feature:

Userid
------
Pyramid framework provides
:class:`pyramid.authentication.SessionAuthenticationPolicy` that stores
user ID in the session. The problem is that the interaction
between the policy and the session is not explicit: user ID is treated like
any other session dict key. While we could always treat the user ID key as 
a special guest, explicit interaction is a much better idea: ::

  # Read
  who = request.session.userid
  # Write
  request.session.userid = 123
  # What could happen when you "forget" the user.
  request.session.userid = None
 
The feature allows to *explicitly* associate sessions with users:

1. User ID is stored in a dedicated session table column. This brings some
   important advantages:

   * you can query sessions by user. For example, you can invalidate all 
     sessions of a user, or show the user his "login sessions".
     
   * you can eager-load additional data the current :term:`view` may require.
     Just configure some eager-loading relationships on your model and some
     of your views will only run a single query per request.

2. The library provides :class:`.UserSessionAuthenticationPolicy` that uses 
   the explicit API of this feature.

.. note::
  The library will not register :class:`.UserSessionAuthenticationPolicy`
  as the authentication policy automatically. You have to do it yourself.


.. _csrf-feature:

CSRF
----
The feature allows to store CSRF token in the dedicated session table column.
You can work with it using ``session.new_csrf_token()`` and 
``session.get_csrf_token()`` methods.

.. note:: CSRF session API has been deprecated since Pyramid 1.9, but in case
  you need it, you can still use this optional feature.



