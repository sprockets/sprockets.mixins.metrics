import asyncio
import contextlib
import logging
import os
import socket
import time

from tornado import iostream

LOGGER = logging.getLogger(__name__)

SETTINGS_KEY = 'sprockets.mixins.metrics.statsd'
"""``self.settings`` key that configures this mix-in."""


class StatsdMixin:
    """Mix this class in to record metrics to a Statsd server."""

    def record_timing(self, duration, *path):
        """Record a timing.

        This method records a timing to the application's namespace
        followed by a calculated path.  Each element of `path` is
        converted to a string and normalized before joining the
        elements by periods.  The normalization process is little
        more than replacing periods with dashes.

        :param float duration: timing to record in seconds
        :param path: elements of the metric path to record

        """
        client = get_client(self.application)
        if client is not None:
            client.send(path, duration * 1000.0, 'ms')

    def increase_counter(self, *path, **kwargs):
        """Increase a counter.

        This method increases a counter within the application's
        namespace.  Each element of `path` is converted to a string
        and normalized before joining the elements by periods.  The
        normalization process is little more than replacing periods
        with dashes.

        :param path: elements of the metric path to incr
        :keyword int amount: amount to increase the counter by.  If
            omitted, the counter is increased by one.

        """
        client = get_client(self.application)
        if client is not None:
            client.send(path, kwargs.get('amount', '1'), 'c')

    @contextlib.contextmanager
    def execution_timer(self, *path):
        """
        Record the time it takes to perform an arbitrary code block.

        :param path: elements of the metric path to record

        This method returns a context manager that records the amount
        of time spent inside of the context and submits a timing metric
        to the specified `path` using (:meth:`record_timing`).

        """
        start = time.time()
        try:
            yield
        finally:
            self.record_timing(max(start, time.time()) - start, *path)

    def on_finish(self):
        """
        Records the time taken to process the request.

        This method records the amount of time taken to process the request
        (as reported by
        :meth:`~tornado.httputil.HTTPServerRequest.request_time`) under the
        path defined by the class's module, it's name, the request method,
        and the status code.  The :meth:`.record_timing` method is used
        to send the metric, so the configured namespace is used as well.

        """
        super().on_finish()
        self.record_timing(self.request.request_time(),
                           self.__class__.__name__, self.request.method,
                           self.get_status())


class StatsDCollector:
    """Collects and submits stats to StatsD.

    This class should be constructed using the :func:`.install` function.
    When installed, it is attached to the :class:`~tornado.web.Application`
    instance for your web application.

    :param str host: The StatsD host
    :param str port: The StatsD port
    :param str protocol: The StatsD protocol. May be either ``udp`` or ``tcp``.
    :param str namespace: The StatsD bucket to write metrics into.
    :param bool prepend_metric_type: Optional flag to prepend bucket path
        with the StatsD metric type

    """
    METRIC_TYPES = {'c': 'counters',
                    'ms': 'timers'}

    def __init__(self, host, port, protocol='udp', namespace='sprockets',
                 prepend_metric_type=True):
        self._host = host
        self._port = int(port)
        self._address = (self._host, self._port)
        self._namespace = namespace
        self._prepend_metric_type = prepend_metric_type
        self._tcp_reconnect_sleep = 5
        self._closing = False

        if protocol == 'tcp':
            self._tcp = True
            self._msg_format = '{path}:{value}|{metric_type}\n'
            self._sock = self._tcp_socket()
        elif protocol == 'udp':
            self._tcp = False
            self._msg_format = '{path}:{value}|{metric_type}'
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        else:
            raise ValueError('Invalid protocol: {}'.format(protocol))

    def _tcp_socket(self):
        """Connect to statsd via TCP and return the IOStream handle.
        :rtype: iostream.IOStream
        """
        sock = iostream.IOStream(socket.socket(
                    socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP))
        sock.connect(self._address)
        sock.set_close_callback(self._tcp_on_closed)
        return sock

    async def _tcp_on_closed(self):
        """Invoked when the socket is closed."""
        if self._closing:
            LOGGER.info('Statsd socket closed')
        else:
            LOGGER.warning('Not connected to statsd, connecting in %s seconds',
                           self._tcp_reconnect_sleep)
            await asyncio.sleep(self._tcp_reconnect_sleep)
            self._sock = self._tcp_socket()

    def close(self):
        """Gracefully close the socket."""
        if not self._closing:
            self._closing = True
            self._sock.close()

    def send(self, path, value, metric_type):
        """Send a metric to Statsd.

        :param list path: The metric path to record
        :param mixed value: The value to record
        :param str metric_type: The metric type

        """
        msg = self._msg_format.format(
            path=self._build_path(path, metric_type),
            value=value,
            metric_type=metric_type)

        LOGGER.debug('Sending %s to %s:%s', msg.encode('ascii'),
                     self._host, self._port)

        try:
            if self._tcp:
                if self._sock.closed():
                    return
                return self._sock.write(msg.encode('ascii'))

            self._sock.sendto(msg.encode('ascii'), (self._host, self._port))
        except iostream.StreamClosedError as error:  # pragma: nocover
            LOGGER.warning('Error sending TCP statsd metric: %s', error)
        except (OSError, socket.error) as error:  # pragma: nocover
            LOGGER.exception('Error sending statsd metric: %s', error)

    def _build_path(self, path, metric_type):
        """Return a normalized path.

        :param list path: elements of the metric path to record
        :param str metric_type: The metric type
        :rtype: str

        """
        path = self._get_prefixes(metric_type) + list(path)
        return '{}.{}'.format(self._namespace,
                              '.'.join(str(p).replace('.', '-') for p in path))

    def _get_prefixes(self, metric_type):
        """Get prefixes where applicable

        Add metric prefix counters, timers respectively if
        :attr:`prepend_metric_type` flag is True.

        :param str metric_type: The metric type
        :rtype: list

        """
        prefixes = []
        if self._prepend_metric_type:
            prefixes.append(self.METRIC_TYPES[metric_type])
        return prefixes


def install(application, **kwargs):
    """Call this to install StatsD for the Tornado application.

    :param tornado.web.Application application: the application to
        install the collector into.
    :param kwargs: keyword parameters to pass to the
        :class:`.StatsDCollector` initializer.
    :returns: :data:`True` if the client was installed successfully,
        or :data:`False` otherwise.

    - **host** The StatsD host. If host is not specified, the
        ``STATSD_HOST`` environment variable, or default `127.0.0.1`,
        will be pass into the :class:`.StatsDCollector`.
    - **port** The StatsD port. If port is not specified, the
        ``STATSD_PORT`` environment variable, or default `8125`,
        will be pass into the :class:`.StatsDCollector`.
    - **namespace** The StatsD bucket to write metrics into.

    """
    if getattr(application, 'statsd', None) is not None:
        LOGGER.warning('Statsd collector is already installed')
        return False

    if 'host' not in kwargs:
        kwargs['host'] = os.environ.get('STATSD_HOST', '127.0.0.1')
    if 'port' not in kwargs:
        kwargs['port'] = os.environ.get('STATSD_PORT', '8125')

    if 'protocol' not in kwargs:
        kwargs['protocol'] = os.environ.get('STATSD_PROTOCOL', 'udp')

    setattr(application, 'statsd', StatsDCollector(**kwargs))
    return True


def get_client(application):
    """Fetch the statsd client if it is installed.

    :rtype: .StatsDCollector

    """
    return getattr(application, 'statsd', None)
