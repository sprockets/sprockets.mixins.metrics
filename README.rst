sprockets.mixins.metrics
========================
Adjust counter and timer metrics in InfluxDB or Graphite using the same API.

.. code-block:: python

   from sprockets.mixins import mediatype, metrics
   from tornado import gen, web
   import queries

   class MyHandler(metrics.StatsdMixin, mediatype.ContentMixin,
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

This simple handler will emit a timer metric that identifies each call to the
``get`` method as well as a separate metric for the database query.  Switching
from using `statsd`_ to `InfluxDB`_ is simply a matter of switch from the
``metrics.StatsdMixin`` to the ``metrics.InfluxDBMixin``.

The mix-in is configured through the ``tornado.web.Application`` settings
property using a key defined by the specific mix-in.  The following snippet
configures the StatsD mix-in from common environment variables:

.. code-block:: python

   import os

   from sprockets.mixins import metrics
   from tornado import web

   def make_application():
       settings = {
           metrics.StatsdMixin.SETTINGS_KEY: {
               'namespace': 'my-application',
               'host': os.environ.get('STATSD_HOST', '127.0.0.1'),
               'port': os.environ.get('STATSD_PORT', '8125'),
           }
       }
       return web.Application([
           # insert handlers here
       ], **settings)


Development Quickstart
----------------------
.. code-block:: bash

   $ python3.4 -mvenv env
   $ . ./env/bin/activate
   (env)$ env/bin/pip install -r requires/development.txt
   (env)$ nosetests
   test_that_cached_socket_is_used (tests.StatsdMethodTimingTests) ... ok
   test_that_counter_accepts_increment_value (tests.StatsdMethodTimingTests) ... ok
   test_that_counter_increment_defaults_to_one (tests.StatsdMethodTimingTests) ... ok
   test_that_default_prefix_is_stored (tests.StatsdMethodTimingTests) ... ok
   test_that_execution_timer_records_time_spent (tests.StatsdMethodTimingTests) ... ok
   test_that_http_method_call_is_recorded (tests.StatsdMethodTimingTests) ... ok

   ----------------------------------------------------------------------
   Ran 6 tests in 1.089s

   OK
   (env)$ ./setup.py build_sphinx -q
   running build_sphinx
   (env)$ open build/sphinx/html/index.html

.. _statsd: https://github.com/etsy/statsd
.. _InfluxDB: https://influxdata.com
