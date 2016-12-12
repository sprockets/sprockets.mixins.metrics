import contextlib
import logging
import os
import socket
import time

LOGGER = logging.getLogger(__name__)

SETTINGS_KEY = 'sprockets.mixins.metrics.statsd'
"""``self.settings`` key that configures this mix-in."""


class StatsdMixin(object):
    """Mix this class in to record metrics to a Statsd server."""

    def initialize(self):
        super(StatsdMixin, self).initialize()
        self.__status_code = None

    def set_metric_tag(self, tag, value):
        """Ignored for statsd since it does not support tagging.

        :param str tag: name of the tag to set
        :param str value: value to assign

        """
        pass

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
        self.application.statsd.send(path, duration * 1000.0, 'ms')

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
        self.application.statsd.send(path, kwargs.get('amount', '1'), 'c')

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
        super(StatsdMixin, self).on_finish()
        self.record_timing(self.request.request_time(),
                           self.__class__.__name__, self.request.method,
                           self.__status_code)

    def set_status(self, status_code, reason=None):
        """Extend tornado `set_status` method to track status code
        to avoid referencing the _status internal variable

        :param int status_code: Response status code. If ``reason``
            is ``None``, it must be present in `httplib.responses
            <http.client.responses>`.
        :param string reason: Human-readable reason phrase describing
            the status code. If ``None``, it will be filled in from
            `httplib.responses <http.client.responses>`.
        """
        self.__status_code = status_code
        super(StatsdMixin, self).set_status(status_code, reason=reason)


class StatsDCollector(object):
    """Collects and submits stats to StatsD via UDP socket.

     This class should be constructed using the
    :meth:`~sprockets.mixins.statsd.install` method. When installed,
    it is attached to the :class:`~tornado.web.Application` instance
    for your web application.

    :param str host: The StatsD host
    :param str port: The StatsD port
    :param str namespace: The StatsD bucket to write metrics into.
    :param bool prepend_metric_type: Optional flag to prepend bucket path
        with the StatsD metric type

    """
    METRIC_TYPES = {'c': 'counters',
                    'ms': 'timers'}

    def __init__(self, host, port, namespace='sprockets',
                 prepend_metric_type=True):
        self._host = host
        self._port = int(port)
        self._namespace = namespace
        self._prepend_metric_type = prepend_metric_type
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)

    def send(self, path, value, metric_type):
        """Send a metric to Statsd.

        :param list path: The metric path to record
        :param mixed value: The value to record
        :param str metric_type: The metric type

        """
        msg = '{0}:{1}|{2}'.format(
            self._build_path(path, metric_type), value, metric_type)
        try:
            LOGGER.debug('Sending %s to %s:%s', msg.encode('ascii'),
                         self._host, self._port)
            self._sock.sendto(msg.encode('ascii'), (self._host, self._port))
        except socket.error:
            LOGGER.exception('Error sending StatsD metrics')

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
        :class:`StatsDCollector` initializer.
    :returns: :data:`True` if the client was installed successfully,
        or :data:`False` otherwise.

    - **host** The StatsD host. If host is not specified, the
        ``STATSD_HOST`` environment variable, or default `127.0.0.1`,
        will be pass into the :class:`StatsDCollector`.
    - **port** The StatsD port. If port is not specified, the
        ``STATSD_PORT`` environment variable, or default `8125`,
        will be pass into the :class:`StatsDCollector`.
    - **namespace** The StatsD bucket to write metrics into.

    """
    if getattr(application, 'statsd', None) is not None:
        LOGGER.warning('Statsd collector is already installed')
        return False

    if 'host' not in kwargs:
        kwargs['host'] = os.environ.get('STATSD_HOST', '127.0.0.1')
    if 'port' not in kwargs:
        kwargs['port'] = os.environ.get('STATSD_PORT', '8125')

    setattr(application, 'statsd', StatsDCollector(**kwargs))
    return True
