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
          with self.execution_timer('dbquery.get'):
             result = yield self.db.query('SELECT * FROM foo WHERE id=%s',
                                          obj_id)
          self.send_response(result)

This simple handler will emit a timer metric that identifies each call to the
``get`` method as well as a separate metric for the database query.  Switching
from using `statsd`_ to `InfluxDB`_ is simply a matter of switch from the
``metrics.StatsdMixin`` to the ``metrics.InfluxDBMixin``.

Development Quickstart
----------------------
.. code-block:: bash

   $ python3.4 -mvenv env
   $ . ./env/bin/activate
   (env)$ pip install -r requires/development.txt

.. _statsd: https://github.com/etsy/statsd
.. _InfluxDB: https://influxdata.com
