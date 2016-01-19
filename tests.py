import socket

from tornado import testing, web

from sprockets.mixins import metrics
from sprockets.mixins.metrics.testing import FakeStatsdServer
import examples.statsd


class StatsdMethodTimingTests(testing.AsyncHTTPTestCase):

    def get_app(self):
        self.application = web.Application([
            web.url('/', examples.statsd.SimpleHandler),
        ])
        return self.application

    def setUp(self):
        self.application = None
        super(StatsdMethodTimingTests, self).setUp()
        self.statsd = FakeStatsdServer(self.io_loop)
        self.application.settings[metrics.StatsdMixin.SETTINGS_KEY] = {
            'host': self.statsd.sockaddr[0],
            'port': self.statsd.sockaddr[1],
            'namespace': 'testing',
        }

    def tearDown(self):
        self.statsd.close()
        super(StatsdMethodTimingTests, self).tearDown()

    @property
    def settings(self):
        return self.application.settings[metrics.StatsdMixin.SETTINGS_KEY]

    def test_that_http_method_call_is_recorded(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 204)

        expected = 'testing.SimpleHandler.GET.204:'
        for bin_msg in self.statsd.datagrams:
            text_msg = bin_msg.decode('ascii')
            if text_msg.startswith(expected):
                _, _, tail = text_msg.partition(':')
                measurement, _, measurement_type = tail.partition('|')
                self.assertTrue(250.0 <= float(measurement) < 500.0,
                                '{} looks wrong'.format(measurement))
                self.assertTrue(measurement_type, 'ms')
                break
        else:
            self.fail('Expected metric starting with {} in {!r}'.format(
                expected, self.statsd.datagrams))

    def test_that_cached_socket_is_used(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        self.settings['socket'] = sock
        self.fetch('/')
        self.assertIs(self.settings['socket'], sock)

    def test_that_default_prefix_is_stored(self):
        del self.settings['namespace']
        self.fetch('/')
        self.assertEqual(
            self.settings['namespace'],
            'applications.' + examples.statsd.SimpleHandler.__module__)
