Examples
========

Sending metrics to StatsD
-------------------------
This simple application emits metrics to port 8125 on localhost.  The
mix-in is configured by passing a ``sprockets.mixins.metrics.statsd``
key into the application settings as shown below.

.. literalinclude:: ../examples/statsd.py
   :pyobject: make_application

The request handler is simple.  In fact, there is nothing of interest
there except that it uses :class:`~sprockets.mixins.metrics.StatsdMixin`
as a base class.

.. literalinclude:: ../examples/statsd.py
   :pyobject: SimpleHandler
