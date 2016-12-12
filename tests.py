import base64
import logging
import os
import socket
import time
import unittest
import uuid

from tornado import gen, testing, web
import mock

from sprockets.mixins.metrics import influxdb, statsd
from sprockets.mixins.metrics.testing import (
    FakeInfluxHandler, FakeStatsdServer)
import examples.influxdb
import examples.statsd


class CounterBumper(statsd.StatsdMixin, web.RequestHandler):

    @gen.coroutine
    def get(self, counter, value):
        with self.execution_timer(*counter.split('.')):
            yield gen.sleep(float(value))
        self.set_status(204)
        self.finish()

    def post(self, counter, amount):
        self.increase_counter(*counter.split('.'), amount=int(amount))
        self.set_status(204)


def assert_between(low, value, high):
    if not (low <= value < high):
        raise AssertionError('Expected {} to be between {} and {}'.format(
            value, low, high))


class StatsdMetricCollectionTests(testing.AsyncHTTPTestCase):

    def get_app(self):
        self.application = web.Application([
            web.url('/', examples.statsd.SimpleHandler),
            web.url('/counters/(.*)/([.0-9]*)', CounterBumper),
        ])
        return self.application

    def setUp(self):
        self.application = None
        super(StatsdMetricCollectionTests, self).setUp()
        self.statsd = FakeStatsdServer(self.io_loop)
        statsd.install(self.application, **{'namespace': 'testing',
                                            'host': self.statsd.sockaddr[0],
                                            'port': self.statsd.sockaddr[1],
                                            'prepend_metric_type': True})

    def tearDown(self):
        self.statsd.close()
        super(StatsdMetricCollectionTests, self).tearDown()

    def test_that_http_method_call_is_recorded(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 204)

        expected = 'testing.timers.SimpleHandler.GET.204'
        for path, value, stat_type in self.statsd.find_metrics(expected, 'ms'):
            assert_between(250.0, float(value), 500.0)

    def test_that_counter_increment_defaults_to_one(self):
        response = self.fetch('/', method='POST', body='')
        self.assertEqual(response.code, 204)

        prefix = 'testing.counters.request.path'
        for path, value, stat_type in self.statsd.find_metrics(prefix, 'c'):
            self.assertEqual(int(value), 1)

    def test_that_counter_accepts_increment_value(self):
        response = self.fetch('/counters/path/5', method='POST', body='')
        self.assertEqual(response.code, 204)

        prefix = 'testing.counters.path'
        for path, value, stat_type in self.statsd.find_metrics(prefix, 'c'):
            self.assertEqual(int(value), 5)

    def test_that_execution_timer_records_time_spent(self):
        response = self.fetch('/counters/one.two.three/0.25')
        self.assertEqual(response.code, 204)

        prefix = 'testing.timers.one.two.three'
        for path, value, stat_type in self.statsd.find_metrics(prefix, 'ms'):
            assert_between(250.0, float(value), 300.0)

    def test_that_add_metric_tag_is_ignored(self):
        response = self.fetch('/',
                              headers={'Correlation-ID': 'does not matter'})
        self.assertEqual(response.code, 204)


class StatsdConfigurationTests(testing.AsyncHTTPTestCase):

    def get_app(self):
        self.application = web.Application([
            web.url('/', examples.statsd.SimpleHandler),
            web.url('/counters/(.*)/([.0-9]*)', CounterBumper),
        ])
        return self.application

    def setUp(self):
        self.application = None
        super(StatsdConfigurationTests, self).setUp()
        self.statsd = FakeStatsdServer(self.io_loop)

        statsd.install(self.application, **{'namespace': 'testing',
                                            'host': self.statsd.sockaddr[0],
                                            'port': self.statsd.sockaddr[1],
                                            'prepend_metric_type': False})

    def tearDown(self):
        self.statsd.close()
        super(StatsdConfigurationTests, self).tearDown()

    def test_that_http_method_call_is_recorded(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 204)

        expected = 'testing.SimpleHandler.GET.204'
        for path, value, stat_type in self.statsd.find_metrics(expected, 'ms'):
            assert_between(250.0, float(value), 500.0)

    def test_that_counter_accepts_increment_value(self):
        response = self.fetch('/counters/path/5', method='POST', body='')
        self.assertEqual(response.code, 204)

        prefix = 'testing.path'
        for path, value, stat_type in self.statsd.find_metrics(prefix, 'c'):
            self.assertEqual(int(value), 5)


class StatsdInstallationTests(unittest.TestCase):

    def setUp(self):
        self.application = web.Application([
            web.url('/', examples.statsd.SimpleHandler),
        ])

    def test_collecter_is_not_reinstalled(self):
        self.assertTrue(statsd.install(self.application))
        self.assertFalse(statsd.install(self.application))

    def test_host_is_used(self):
        statsd.install(self.application, **{'host': 'example.com'})
        self.assertEqual(self.application.statsd._host, 'example.com')

    def test_port_is_used(self):
        statsd.install(self.application, **{'port': '8888'})
        self.assertEqual(self.application.statsd._port, 8888)

    def test_default_host_and_port_is_used(self):
        statsd.install(self.application, **{'namespace': 'testing'})
        self.assertEqual(self.application.statsd._host, '127.0.0.1')
        self.assertEqual(self.application.statsd._port, 8125)


class InfluxDbTests(testing.AsyncHTTPTestCase):

    def get_app(self):
        self.application = web.Application([
            web.url(r'/', examples.influxdb.SimpleHandler),
            web.url(r'/write', FakeInfluxHandler),
        ])
        influxdb.install(self.application, **{'database': 'requests',
                                              'submission_interval': 1,
                                              'url': self.get_url('/write')})
        self.application.influx_db = {}
        return self.application

    def setUp(self):
        self.application = None
        super(InfluxDbTests, self).setUp()
        self.application.settings[influxdb.SETTINGS_KEY] = {
            'measurement': 'my-service'
        }
        logging.getLogger(FakeInfluxHandler.__module__).setLevel(logging.DEBUG)

    @gen.coroutine
    def tearDown(self):
        yield influxdb.shutdown(self.application)
        super(InfluxDbTests, self).tearDown()

    @property
    def influx_messages(self):
        return FakeInfluxHandler.get_messages(self.application, self)

    def test_that_http_method_call_details_are_recorded(self):
        start = int(time.time())
        response = self.fetch('/')
        self.assertEqual(response.code, 204)

        for key, fields, timestamp, _headers in self.influx_messages:
            if key.startswith('my-service,'):
                tag_dict = dict(a.split('=') for a in key.split(',')[1:])
                self.assertEqual(tag_dict['handler'],
                                 'examples.influxdb.SimpleHandler')
                self.assertEqual(tag_dict['method'], 'GET')
                self.assertEqual(tag_dict['hostname'], socket.gethostname())
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

        for key, fields, timestamp, _headers in self.influx_messages:
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

        for key, fields, timestamp, _headers in self.influx_messages:
            if key.startswith('my-service,'):
                value_dict = dict(a.split('=') for a in fields.split(','))
                self.assertEqual(int(value_dict['slept']), 42)
                break
        else:
            self.fail('Expected to find "request" metric in {!r}'.format(
                      list(self.application.influx_db['requests'])))

    def test_that_cached_db_connection_is_used(self):
        cfg = self.application.settings[influxdb.SETTINGS_KEY]
        conn = mock.Mock()
        cfg['db_connection'] = conn
        response = self.fetch('/')
        self.assertEqual(response.code, 204)
        self.assertIs(cfg['db_connection'], conn)

    def test_that_metric_tag_is_tracked(self):
        cid = str(uuid.uuid4())
        response = self.fetch('/', headers={'Correlation-ID': cid})
        self.assertEqual(response.code, 204)

        for key, fields, timestamp, _headers in self.influx_messages:
            if key.startswith('my-service,'):
                tag_dict = dict(a.split('=') for a in key.split(',')[1:])
                self.assertEqual(tag_dict['correlation_id'], cid)
                break
        else:
            self.fail('Expected to find "request" metric in {!r}'.format(
                      list(self.application.influx_db['requests'])))

    def test_metrics_with_buffer_not_flush(self):
        self.application.settings[influxdb] = {
            'measurement': 'my-service'
        }

        # 2 requests
        response = self.fetch('/')
        self.assertEqual(response.code, 204)
        response = self.fetch('/')
        self.assertEqual(response.code, 204)
        with self.assertRaises(AssertionError):
            self.assertEqual(0, len(self.influx_messages))


class InfluxDbAuthTests(testing.AsyncHTTPTestCase):

    def setUp(self):
        self.application = None
        self.username, self.password = str(uuid.uuid4()), str(uuid.uuid4())
        os.environ['INFLUX_USER'] = self.username
        os.environ['INFLUX_PASSWORD'] = self.password
        super(InfluxDbAuthTests, self).setUp()
        self.application.settings[influxdb.SETTINGS_KEY] = {
            'measurement': 'my-service'
        }
        logging.getLogger(FakeInfluxHandler.__module__).setLevel(logging.DEBUG)

    @gen.coroutine
    def tearDown(self):
        yield influxdb.shutdown(self.application)
        super(InfluxDbAuthTests, self).tearDown()

    @property
    def influx_messages(self):
        return FakeInfluxHandler.get_messages(self.application, self)

    def get_app(self):
        self.application = web.Application([
            web.url(r'/', examples.influxdb.SimpleHandler),
            web.url(r'/write', FakeInfluxHandler),
        ])
        influxdb.install(self.application, **{'database': 'requests',
                                              'submission_interval': 1,
                                              'url': self.get_url('/write')})
        self.application.influx_db = {}
        return self.application

    def test_that_authentication_header_was_sent(self):
        print(os.environ)
        response = self.fetch('/')
        self.assertEqual(response.code, 204)

        for _key, _fields, _timestamp, headers in self.influx_messages:
            self.assertIn('Authorization', headers)
            scheme, value = headers['Authorization'].split(' ')
            self.assertEqual(scheme, 'Basic')
            temp = base64.b64decode(value.encode('utf-8'))
            values = temp.decode('utf-8').split(':')
            self.assertEqual(values[0], self.username)
            self.assertEqual(values[1], self.password)
            break
        else:
            self.fail('Did not have an Authorization header')
