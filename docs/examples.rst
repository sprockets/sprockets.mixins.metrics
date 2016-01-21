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

Sending measurements to InfluxDB
--------------------------------
This simple application sends per-request measurements to an InfluxDB
server listening on ``localhost``.  The mix-in is configured by passing
a ``sprockets.mixins.metrics.influxdb`` key into the application settings
as shown below.

.. literalinclude:: ../examples/influxdb.py
   :pyobject: make_application

The InfluxDB database and measurement name are also configured in the
application settings object.  The request handler is responsible for
providing the tag and value portions of the measurement.  The standard
:class:`Metric Mixin API<sprockets.mixins.metrics.Mixin>` is used to set
tagged values.

.. literalinclude:: ../examples/influxdb.py
   :pyobject: SimpleHandler
