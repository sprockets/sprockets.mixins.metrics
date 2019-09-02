import asyncio
import itertools
import socket
import unittest.mock

from tornado import iostream, testing, web

from sprockets.mixins.metrics import statsd
from sprockets.mixins.metrics.testing import FakeStatsdServer
import examples.statsd


class CounterBumper(statsd.StatsdMixin, web.RequestHandler):

    async def get(self, counter, value):
        with self.execution_timer(*counter.split('.')):
            await asyncio.sleep(float(value))
        self.set_status(204)
        self.finish()

    def post(self, counter, amount):
        self.increase_counter(*counter.split('.'), amount=int(amount))
        self.set_status(204)


class DefaultStatusCode(statsd.StatsdMixin, web.RequestHandler):

    def get(self):
        pass


def assert_between(low, value, high):
    if not (low <= value < high):
        raise AssertionError('Expected {} to be between {} and {}'.format(
            value, low, high))


class MisconfiguredStatsdMetricCollectionTests(testing.AsyncHTTPTestCase):

    def get_app(self):
        self.application = web.Application([
            web.url('/', examples.statsd.SimpleHandler),
            web.url('/counters/(.*)/([.0-9]*)', CounterBumper),
            web.url('/status_code', DefaultStatusCode),
        ])

    def test_bad_protocol_raises_ValueError(self):
        with self.assertRaises(ValueError):
            statsd.StatsDCollector(host='127.0.0.1',
                                   port='8125',
                                   protocol='bad_protocol')


class TCPStatsdMetricCollectionTests(testing.AsyncHTTPTestCase):

    def get_app(self):
        self.application = web.Application([
            web.url('/', examples.statsd.SimpleHandler),
            web.url('/counters/(.*)/([.0-9]*)', CounterBumper),
            web.url('/status_code', DefaultStatusCode),
        ])
        return self.application

    def setUp(self):
        self.application = None
        self.namespace = 'testing'

        super().setUp()
        self.statsd = FakeStatsdServer(self.io_loop, protocol='tcp')

        statsd.install(self.application, **{'namespace': self.namespace,
                                            'host': self.statsd.sockaddr[0],
                                            'port': self.statsd.sockaddr[1],
                                            'protocol': 'tcp',
                                            'prepend_metric_type': True})

    @unittest.mock.patch.object(iostream.IOStream, 'write')
    def test_write_not_executed_when_connection_is_closed(self, mock_write):
        self.application.statsd._sock.close()
        self.application.statsd.send('foo', 500, 'c')
        mock_write.assert_not_called()

    @unittest.mock.patch.object(iostream.IOStream, 'write')
    def test_expected_counters_data_written(self, mock_sock):
        path = ('foo', 'bar')
        value = 500
        metric_type = 'c'
        expected = "{}:{}|{}\n".format('.'.join(
                    itertools.chain((self.namespace, 'counters'), path)),
                    value,
                    metric_type)

        self.application.statsd.send(path, value, metric_type)
        mock_sock.assert_called_once_with(expected.encode())

    @unittest.mock.patch.object(iostream.IOStream, 'write')
    def test_expected_timers_data_written(self, mock_sock):
        path = ('foo', 'bar')
        value = 500
        metric_type = 'ms'
        expected = "{}:{}|{}\n".format('.'.join(
                    itertools.chain((self.namespace, 'timers'), path)),
                    value,
                    metric_type)

        self.application.statsd.send(path, value, metric_type)
        mock_sock.assert_called_once_with(expected.encode())

    def test_tcp_message_format(self):
        expected = '{path}:{value}|{metric_type}\n'
        self.assertEqual(self.application.statsd._msg_format, expected)

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

    def test_that_status_code_is_used_when_not_explicitly_set(self):
        response = self.fetch('/status_code')
        self.assertEqual(response.code, 200)

        expected = 'testing.timers.DefaultStatusCode.GET.200'
        self.assertEqual(expected,
                         list(self.statsd.find_metrics(expected, 'ms'))[0][0])

    def test_reconnect_logic(self):
        self.application.statsd._tcp_reconnect_sleep = 0.05
        self.application.statsd._sock.close()
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.075))
        response = self.fetch('/status_code')
        self.assertEqual(response.code, 200)

    def test_that_mixin_works_without_client(self):
        self.application.statsd.close()
        delattr(self.application, 'statsd')

        response = self.fetch('/', method='POST', body='')
        self.assertEqual(response.code, 204)


class TCPStatsdConfigurationTests(testing.AsyncHTTPTestCase):

    def get_app(self):
        self.application = web.Application([
            web.url('/', examples.statsd.SimpleHandler),
            web.url('/counters/(.*)/([.0-9]*)', CounterBumper),
        ])
        return self.application

    def setUp(self):
        self.application = None
        self.namespace = 'testing'

        super().setUp()
        self.statsd = FakeStatsdServer(self.io_loop, protocol='tcp')

        statsd.install(self.application, **{'namespace': self.namespace,
                                            'host': self.statsd.sockaddr[0],
                                            'port': self.statsd.sockaddr[1],
                                            'protocol': 'tcp',
                                            'prepend_metric_type': False})

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


class UDPStatsdMetricCollectionTests(testing.AsyncHTTPTestCase):

    def get_app(self):
        self.application = web.Application([
            web.url('/', examples.statsd.SimpleHandler),
            web.url('/counters/(.*)/([.0-9]*)', CounterBumper),
            web.url('/status_code', DefaultStatusCode),
        ])
        return self.application

    def setUp(self):
        self.application = None
        self.namespace = 'testing'

        super().setUp()
        self.statsd = FakeStatsdServer(self.io_loop, protocol='udp')

        statsd.install(self.application, **{'namespace': self.namespace,
                                            'host': self.statsd.sockaddr[0],
                                            'port': self.statsd.sockaddr[1],
                                            'protocol': 'udp',
                                            'prepend_metric_type': True})

    def tearDown(self):
        self.statsd.close()
        super().tearDown()

    @unittest.mock.patch.object(socket.socket, 'sendto')
    def test_expected_counters_data_written(self, mock_sock):
        path = ('foo', 'bar')
        value = 500
        metric_type = 'c'
        expected = "{}:{}|{}".format('.'.join(
                    itertools.chain((self.namespace, 'counters'), path)),
                    value,
                    metric_type)

        self.application.statsd.send(path, value, metric_type)
        mock_sock.assert_called_once_with(
                expected.encode(),
                (self.statsd.sockaddr[0], self.statsd.sockaddr[1]))

    @unittest.mock.patch.object(socket.socket, 'sendto')
    def test_expected_timers_data_written(self, mock_sock):
        path = ('foo', 'bar')
        value = 500
        metric_type = 'ms'
        expected = "{}:{}|{}".format('.'.join(
                    itertools.chain((self.namespace, 'timers'), path)),
                    value,
                    metric_type)

        self.application.statsd.send(path, value, metric_type)
        mock_sock.assert_called_once_with(
                expected.encode(),
                (self.statsd.sockaddr[0], self.statsd.sockaddr[1]))

    def test_udp_message_format(self):
        expected = '{path}:{value}|{metric_type}'
        self.assertEqual(self.application.statsd._msg_format, expected)

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

    def test_that_status_code_is_used_when_not_explicitly_set(self):
        response = self.fetch('/status_code')
        self.assertEqual(response.code, 200)

        expected = 'testing.timers.DefaultStatusCode.GET.200'
        self.assertEqual(expected,
                         list(self.statsd.find_metrics(expected, 'ms'))[0][0])

    def test_that_mixin_works_without_client(self):
        self.application.statsd.close()
        delattr(self.application, 'statsd')

        response = self.fetch('/', method='POST', body='')
        self.assertEqual(response.code, 204)


class UDPStatsdConfigurationTests(testing.AsyncHTTPTestCase):

    def get_app(self):
        self.application = web.Application([
            web.url('/', examples.statsd.SimpleHandler),
            web.url('/counters/(.*)/([.0-9]*)', CounterBumper),
        ])
        return self.application

    def setUp(self):
        self.application = None
        self.namespace = 'testing'

        super().setUp()
        self.statsd = FakeStatsdServer(self.io_loop, protocol='udp')

        statsd.install(self.application, **{'namespace': self.namespace,
                                            'host': self.statsd.sockaddr[0],
                                            'port': self.statsd.sockaddr[1],
                                            'protocol': 'udp',
                                            'prepend_metric_type': False})

    def tearDown(self):
        self.statsd.close()
        super().tearDown()

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
