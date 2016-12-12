sprockets.mixins.metrics
========================
Adjust counter and timer metrics in `InfluxDB`_ or `StatsD`_ using the same API.

The mix-in is configured through the ``tornado.web.Application`` settings
property using a key defined by the specific mix-in.

Statsd Mixin
------------

The following snippet configures the StatsD mix-in from common environment
variables. This simple handler will emit a timer metric that identifies each
call to the ``get`` method as well as a separate metric for the database query.

.. code-block:: python

   import os

   from sprockets.mixins import mediatype
   from sprockets.mixins.metrics import statsd
   from tornado import gen, web
   import queries

   def make_application():
       application = web.Application([
           web.url(r'/', MyHandler),
       ], **settings)

       statsd.install({'namespace': 'my-application',
                       'host': os.environ.get('STATSD_HOST', '127.0.0.1'),
                       'port': os.environ.get('STATSD_PORT', '8125')})
       return application

   class MyHandler(statsd.StatsdMixin,
                   mediatype.ContentMixin,
                   web.RequestHandler):

       def initialize(self):
           super(MyHandler, self).initialize()
           self.db = queries.TornadoSession(os.environ['MY_PGSQL_DSN'])

       @gen.coroutine
       def get(self, obj_id):
           with self.execution_timer('dbquery', 'get'):
              result = yield self.db.query('SELECT * FROM foo WHERE id=%s',
                                           obj_id)
           self.send_response(result)

Settings
^^^^^^^^

:namespace: The namespace for the measurements
:host: The Statsd host
:port: The Statsd port
:prepend_metric_type: Optional flag to prepend bucket path with the StatsD
    metric type

InfluxDB Mixin
--------------

The following snippet configures the InfluxDB mix-in from common environment
variables:

.. code-block:: python

   import os

   from sprockets.mixins.metrics import influxdb
   from sprockets.mixins import postgresql
   from tornado import gen, web

   def make_app(**settings):
       settings[influxdb.SETTINGS_KEY] = {
           'measurement': 'rollup',
       }

       application = web.Application(
           [
               web.url(r'/', MyHandler),
           ], **settings)

       influxdb.install({'url': 'http://localhost:8086',
                         'database': 'tornado-app'})
       return application


   class MyHandler(influxdb.InfluxDBMixin,
                   postgresql.HandlerMixin,
                   web.RequestHandler):

       @gen.coroutine
       def get(self, obj_id):
           with self.execution_timer('dbquery', 'get'):
              result = yield self.postgresql_session.query(
                  'SELECT * FROM foo WHERE id=%s', obj_id)
           self.send_response(result)

If your application handles signal handling for shutdowns, the
:meth:`~sprockets.mixins.influxdb.shutdown` method will try to cleanly ensure
that any buffered metrics in the InfluxDB collector are written prior to
shutting down. The method returns a :class:`~tornado.concurrent.TracebackFuture`
that should be waited on prior to shutting down.

For environment variable based configuration, use the ``INFLUX_SCHEME``,
``INFLUX_HOST``, and ``INFLUX_PORT`` environment variables.  The defaults are
``https``, ``localhost``, and ``8086`` respectively.

To use authentication with InfluxDB, set the ``INFLUX_USER`` and the
``INFLUX_PASSWORD`` environment variables. Once installed, the
``INFLUX_PASSWORD`` value will be masked in the Python process.

Settings
^^^^^^^^

:url: The InfluxDB API URL
:database: the database to write measurements into
:submission_interval: How often to submit metric batches in
   milliseconds. Default: ``5000``
:max_batch_size: The number of measurements to be submitted in a
   single HTTP request. Default: ``1000``
:tags: Default tags that are to be submitted with each metric. The tag
   ``hostname`` is added by default along with ``environment`` and ``service``
   if the corresponding ``ENVIRONMENT`` or ``SERVICE`` environment variables
   are set.
:auth_username: A username to use for InfluxDB authentication, if desired.
:auth_password: A password to use for InfluxDB authentication, if desired.

Development Quickstart
----------------------
.. code-block:: bash

   $ python3.4 -mvenv env
   $ . ./env/bin/activate
   (env)$ env/bin/pip install -r requires/development.txt
   (env)$ nosetests
   test_metrics_with_buffer_not_flush (tests.InfluxDbTests) ... ok
   test_that_cached_db_connection_is_used (tests.InfluxDbTests) ... ok
   test_that_counter_is_tracked (tests.InfluxDbTests) ... ok
   test_that_execution_timer_is_tracked (tests.InfluxDbTests) ... ok
   test_that_http_method_call_details_are_recorded (tests.InfluxDbTests) ... ok
   test_that_metric_tag_is_tracked (tests.InfluxDbTests) ... ok
   test_that_add_metric_tag_is_ignored (tests.StatsdMethodTimingTests) ... ok
   test_that_cached_socket_is_used (tests.StatsdMethodTimingTests) ... ok
   test_that_counter_accepts_increment_value (tests.StatsdMethodTimingTests) ... ok
   test_that_counter_increment_defaults_to_one (tests.StatsdMethodTimingTests) ... ok
   test_that_default_prefix_is_stored (tests.StatsdMethodTimingTests) ... ok
   test_that_execution_timer_records_time_spent (tests.StatsdMethodTimingTests) ... ok
   test_that_http_method_call_is_recorded (tests.StatsdMethodTimingTests) ... ok

   ----------------------------------------------------------------------
   Ran 13 tests in 3.572s

   OK
   (env)$ ./setup.py build_sphinx -q
   running build_sphinx
   (env)$ open build/sphinx/html/index.html

.. _StatsD: https://github.com/etsy/statsd
.. _InfluxDB: https://influxdata.com
