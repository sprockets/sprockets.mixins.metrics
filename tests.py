import socket

from tornado import testing, web

from sprockets.mixins import metrics
from sprockets.mixins.metrics.testing import FakeStatsdServer
import examples.statsd


class CounterBumper(metrics.StatsdMixin, web.RequestHandler):

    def post(self, counter, amount):
        path = counter.split('.')
        self.increase_counter(*path, amount=int(amount))
        self.set_status(204)


class StatsdMethodTimingTests(testing.AsyncHTTPTestCase):

    def get_app(self):
        self.application = web.Application([
            web.url('/', examples.statsd.SimpleHandler),
            web.url('/counters/(\w*)/(\d*)', CounterBumper),
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

        expected = 'testing.SimpleHandler.GET.204'
        for path, value, stat_type in self.statsd.find_metrics(expected, 'ms'):
            self.assertTrue(250.0 <= float(value) < 500.0,
                            '{} looks wrong'.format(value))

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

    def test_that_counter_increment_defaults_to_one(self):
        response = self.fetch('/', method='POST', body='')
        self.assertEqual(response.code, 204)

        prefix = 'testing.request.path'
        for path, value, stat_type in self.statsd.find_metrics(prefix, 'c'):
            self.assertEqual(int(value), 1)

    def test_that_counter_accepts_increment_value(self):
        response = self.fetch('/counters/path/5', method='POST', body='')
        self.assertEqual(response.code, 204)

        prefix = 'testing.path'
        for path, value, stat_type in self.statsd.find_metrics(prefix, 'c'):
            self.assertEqual(int(value), 5)
