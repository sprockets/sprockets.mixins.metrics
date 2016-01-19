Reference Documentation
=======================
This library defines mix-ins that record application metrics.  Each mix-in
implements the same interface:

.. class:: sprockets.mixins.metrics.Mixin

   .. data:: SETTINGS_KEY

      Key in ``self.application.settings`` that contains this particular
      mix-in's configuration data.

   .. method:: record_timing(duration, *path)
      :noindex:

      :param float duration: number of seconds to record
      :param path: timing path to record

      .. code-block:: python

         self.record_timing(self.request.request_time(), 'request', 'lookup')

   .. method:: increase_counter(*path, amount=1)

      :param path: counter path to increment
      :keyword int amount: value to increase the counter by

      .. code-block:: python

         self.increase_counter('db', 'query', 'foo')

   .. method:: execution_timer(*path)

      :param path: timing path to record

      This method returns a context manager that records a timing
      metric to the specified path.

      .. code-block:: python

         with self.execution_timer('db', 'query', 'foo'):
             rows = yield self.session.query('SELECT * FROM foo')


Statsd Implementation
---------------------
.. autoclass:: sprockets.mixins.metrics.StatsdMixin
   :members:

Testing Helpers
---------------
*So who actually tests that their metrics are emitted as they expect?*

Usually the answer is *no one*.  Why is that?  The ``testing`` module
contains some helper that make testing a little easier.

.. autoclass:: sprockets.mixins.metrics.testing.FakeStatsdServer
   :members:
