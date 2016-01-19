Reference Documentation
=======================
This library defines mix-ins that record application metrics.  Each mix-in
implements the same interface:

.. class:: sprockets.mixins.metrics.Mixin

   .. data:: SETTINGS_KEY

      Key in ``self.application.settings`` that contains this particular
      mix-in's configuration data.

   .. method:: record_timing(path, milliseconds)

      :param str path: timing path to record
      :param float milliseconds: number of milliseconds to record


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
