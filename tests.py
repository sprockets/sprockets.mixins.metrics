import logging
import socket
import time
import uuid

from tornado import gen, testing, web
import mock

from sprockets.mixins import metrics
from sprockets.mixins.metrics.testing import (
    FakeInfluxHandler, FakeStatsdServer)
import examples.influxdb
import examples.statsd


class CounterBumper(metrics.StatsdMixin, web.RequestHandler):

    @gen.coroutine
    def get(self, counter, time):
        path = counter.split('.')
        with self.execution_timer(*path):
            yield gen.sleep(float(time))
        self.set_status(204)
        self.finish()

    def post(self, counter, amount):
        path = counter.split('.')
        self.increase_counter(*path, amount=int(amount))
        self.set_status(204)


def assert_between(low, value, high):
    if not (low <= value < high):
        raise AssertionError('Expected {} to be between {} and {}'.format(
            value, low, high))


class StatsdMethodTimingTests(testing.AsyncHTTPTestCase):

    def get_app(self):
        self.application = web.Application([
            web.url('/', examples.statsd.SimpleHandler),
            web.url('/counters/(.*)/([.0-9]*)', CounterBumper),
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
            assert_between(250.0, float(value), 500.0)

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

    def test_that_execution_timer_records_time_spent(self):
        response = self.fetch('/counters/one.two.three/0.25')
        self.assertEqual(response.code, 204)

        prefix = 'testing.one.two.three'
        for path, value, stat_type in self.statsd.find_metrics(prefix, 'ms'):
            assert_between(250.0, float(value), 300.0)

    def test_that_add_metric_tag_is_ignored(self):
        response = self.fetch('/',
                              headers={'Correlation-ID': 'does not matter'})
        self.assertEqual(response.code, 204)


class InfluxDbTests(testing.AsyncHTTPTestCase):

    def get_app(self):
        self.application = web.Application([
            web.url(r'/', examples.influxdb.SimpleHandler),
            web.url(r'/write', FakeInfluxHandler),
        ])
        return self.application

    def setUp(self):
        self.application = None
        super(InfluxDbTests, self).setUp()
        self.application.settings[metrics.InfluxDBMixin.SETTINGS_KEY] = {
            'measurement': 'my-service',
            'write_url': self.get_url('/write'),
            'database': 'requests',
        }
        logging.getLogger(FakeInfluxHandler.__module__).setLevel(logging.DEBUG)

    @property
    def influx_messages(self):
        return FakeInfluxHandler.get_messages(self.application,
                                              'requests', self)

    def test_that_http_method_call_details_are_recorded(self):
        start = int(time.time())
        response = self.fetch('/')
        self.assertEqual(response.code, 204)

        for key, fields, timestamp in self.influx_messages:
            if key.startswith('my-service,'):
                tag_dict = dict(a.split('=') for a in key.split(',')[1:])
                self.assertEqual(tag_dict['handler'],
                                 'examples.influxdb.SimpleHandler')
                self.assertEqual(tag_dict['method'], 'GET')
                self.assertEqual(tag_dict['host'], socket.gethostname())
                self.assertEqual(tag_dict['status_code'], '204')

                value_dict = dict(a.split('=') for a in fields.split(','))
                assert_between(0.25, float(value_dict['duration']), 0.3)

                nanos_since_epoch = int(timestamp)
                then = nanos_since_epoch / 1000000000
                assert_between(start, then, time.time())
                break
        else:
            self.fail('Expected to find "request" metric in {!r}'.format(
                list(self.application.influx_db['requests'])))

    def test_that_execution_timer_is_tracked(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 204)

        for key, fields, timestamp in self.influx_messages:
            if key.startswith('my-service,'):
                value_dict = dict(a.split('=') for a in fields.split(','))
                assert_between(0.25, float(value_dict['sleepytime']), 0.3)
                break
        else:
            self.fail('Expected to find "request" metric in {!r}'.format(
                list(self.application.influx_db['requests'])))

    def test_that_counter_is_tracked(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 204)

        for key, fields, timestamp in self.influx_messages:
            if key.startswith('my-service,'):
                value_dict = dict(a.split('=') for a in fields.split(','))
                self.assertEqual(int(value_dict['slept']), 42)
                break
        else:
            self.fail('Expected to find "request" metric in {!r}'.format(
                      list(self.application.influx_db['requests'])))

    def test_that_cached_db_connection_is_used(self):
        cfg = self.application.settings[metrics.InfluxDBMixin.SETTINGS_KEY]
        conn = mock.Mock()
        cfg['db_connection'] = conn
        response = self.fetch('/')
        self.assertEqual(response.code, 204)
        self.assertIs(cfg['db_connection'], conn)

    def test_that_metric_tag_is_tracked(self):
        cid = str(uuid.uuid4())
        response = self.fetch('/', headers={'Correlation-ID': cid})
        self.assertEqual(response.code, 204)

        for key, fields, timestamp in self.influx_messages:
            if key.startswith('my-service,'):
                tag_dict = dict(a.split('=') for a in key.split(',')[1:])
                self.assertEqual(tag_dict['correlation_id'], cid)
                break
        else:
            self.fail('Expected to find "request" metric in {!r}'.format(
                      list(self.application.influx_db['requests'])))
