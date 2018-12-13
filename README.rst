sprockets.mixins.metrics
========================

|Version| |Status| |Coverage| |License|

Adjust counter and timer metrics in `StatsD`_ using the same API.

The mix-in is configured through the ``tornado.web.Application`` settings
property using a key defined by the specific mix-in.

Documentation
-------------
https://sprocketsmixinsmetrics.readthedocs.io


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


.. |Version| image:: https://img.shields.io/pypi/v/sprockets_mixins_metrics.svg
   :target: https://pypi.python.org/pypi/sprockets_mixins_metrics

.. |Status| image:: https://img.shields.io/travis/sprockets/sprockets.mixins.metrics.svg
   :target: https://travis-ci.org/sprockets/sprockets.mixins.metrics

.. |Coverage| image:: https://img.shields.io/codecov/c/github/sprockets/sprockets.mixins.metrics.svg
   :target: https://codecov.io/github/sprockets/sprockets.mixins.metrics?branch=master

.. |License| image:: https://img.shields.io/pypi/l/sprockets_mixins_metrics.svg
   :target: https://github.com/sprockets/sprockets.mixins.metrics/blob/master/LICENSE
