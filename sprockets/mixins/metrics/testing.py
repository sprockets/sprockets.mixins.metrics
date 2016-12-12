import logging
import re
import socket

from tornado import gen, web

LOGGER = logging.getLogger(__name__)
STATS_PATTERN = re.compile(r'(?P<path>[^:]*):(?P<value>[^|]*)\|(?P<type>.*)$')


class FakeStatsdServer(object):
    """
    Implements something resembling a statsd server.

    :param tornado.ioloop.IOLoop iol: the loop to attach to

    Create an instance of this class in your asynchronous test case
    attached to the IOLoop and configure your application to send
    metrics to it.  The received datagrams are available in the
    ``datagrams`` attribute for validation in your tests.

    .. attribute:: sockaddr

       The socket address that the server is listening on.  This is
       a tuple returned from :meth:`socket.socket.getsockname`.

    .. attribute:: datagrams

       A list of datagrams that have been received by the server.

    """

    def __init__(self, iol):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                                    socket.IPPROTO_UDP)
        self.socket.bind(('127.0.0.1', 0))
        self.sockaddr = self.socket.getsockname()
        self.datagrams = []

        iol.add_handler(self.socket, self._handle_events, iol.READ)
        self._iol = iol

    def close(self):
        if self.socket is not None:
            if self._iol is not None:
                self._iol.remove_handler(self.socket)
                self._iol = None
            self.socket.close()
            self.socket = None

    def _handle_events(self, fd, events):
        if fd != self.socket:
            return
        if self._iol is None:
            raise RuntimeError

        if events & self._iol.READ:
            data, _ = self.socket.recvfrom(4096)
            self.datagrams.append(data)

    def find_metrics(self, prefix, metric_type):
        """
        Yields captured datagrams that start with `prefix`.

        :param str prefix: the metric prefix to search for
        :param str metric_type: the statsd metric type (e.g., 'ms', 'c')
        :returns: yields (path, value, metric_type) tuples for each
            captured metric that matches
        :raises AssertionError: if no metrics match.

        """
        pattern = re.compile(
            '(?P<path>{}[^:]*):(?P<value>[^|]*)\\|(?P<type>{})'.format(
                re.escape(prefix), re.escape(metric_type)))
        matched = False
        for datagram in self.datagrams:
            text_msg = datagram.decode('ascii')
            match = pattern.match(text_msg)
            if match:
                yield match.groups()
                matched = True

        if not matched:
            raise AssertionError(
                'Expected metric starting with "{}" in {!r}'.format(
                    prefix, self.datagrams))


class FakeInfluxHandler(web.RequestHandler):
    """
    Request handler that mimics the InfluxDB write endpoint.

    Install this handler into your testing application and configure
    the metrics plugin to write to it.  After running a test, you can
    examine the received measurements by iterating over the
    ``influx_db`` list in the application object.

    .. code-block:: python

       class TestThatMyStuffWorks(testing.AsyncHTTPTestCase):

           def get_app(self):
               self.app = web.Application([
                   web.url('/', HandlerUnderTest),
                   web.url('/write', metrics.testing.FakeInfluxHandler),
               ])
               return self.app

           def setUp(self):
               super(TestThatMyStuffWorks, self).setUp()
               self.app.settings[metrics.InfluxDBMixin.SETTINGS_KEY] = {
                   'measurement': 'stuff',
                   'write_url': self.get_url('/write'),
                   'database': 'requests',
               }

           def test_that_measurements_are_emitted(self):
               self.fetch('/')  # invokes handler under test
               measurements = metrics.testing.FakeInfluxHandler(
                   self.app, 'requests', self)
               for key, fields, timestamp in measurements:
                   # inspect measurements

    """
    def initialize(self):
        super(FakeInfluxHandler, self).initialize()
        self.logger = LOGGER.getChild(__name__)
        if not hasattr(self.application, 'influx_db'):
            self.application.influx_db = {}
        if self.application.influxdb.database not in self.application.influx_db:
            self.application.influx_db[self.application.influxdb.database] = []

    def post(self):
        db = self.get_query_argument('db')
        payload = self.request.body.decode('utf-8')
        for line in payload.splitlines():
            self.logger.debug('received "%s"', line)
            key, fields, timestamp = line.split()
            self.application.influx_db[db].append((key, fields, timestamp,
                                                   self.request.headers))
        self.set_status(204)

    @staticmethod
    def get_messages(application, test_case):
        """
        Wait for measurements to show up and return them.

        :param tornado.web.Application application: application that
            :class:`.FakeInfluxHandler` is writing to
        :param str database: database to retrieve
        :param tornado.testing.AsyncTestCase test_case: test case
            that is being executed
        :return: measurements received as a :class:`list` of
            (key, fields, timestamp) tuples

        Since measurements are sent asynchronously from within the
        ``on_finish`` handler they are usually not sent by the time
        that the test case has stopped the IOloop.  This method accounts
        for this by running the IOloop until measurements have been
        received.  It will raise an assertion error if measurements
        are not received in a reasonable number of runs.

        """
        for _ in range(0, 15):
            if hasattr(application, 'influx_db'):
                if application.influx_db.get(application.influxdb.database):
                    return application.influx_db[application.influxdb.database]
            test_case.io_loop.add_future(gen.sleep(0.1),
                                         lambda _: test_case.stop())
            test_case.wait()
        else:
            test_case.fail('Message not published to InfluxDB before timeout')
