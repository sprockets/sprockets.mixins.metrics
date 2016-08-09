import contextlib
import logging
import os
import socket
import time

from tornado import concurrent, httpclient, ioloop

from sprockets.mixins.metrics import __version__

LOGGER = logging.getLogger(__name__)

SETTINGS_KEY = 'sprockets.mixins.metrics.influxdb'
"""``self.settings`` key that configures this mix-in."""

_USER_AGENT = 'sprockets.mixins.metrics/v{}'.format(__version__)


class InfluxDBMixin(object):
    """Mix this class in to record measurements to a InfluxDB server."""

    def __init__(self, application, request, **kwargs):
        self.__metrics = []
        self.__tags = {
            'handler': '{}.{}'.format(self.__module__,
                                      self.__class__.__name__),
            'method': request.method,
        }

        # Call to super().__init__() needs to be *AFTER* we create our
        # properties since it calls initialize() which may want to call
        # methods like ``set_metric_tag``
        super(InfluxDBMixin, self).__init__(application, request, **kwargs)

    def set_metric_tag(self, tag, value):
        """
        Add a tag to the measurement key.

        :param str tag: name of the tag to set
        :param str value: value to assign

        This will overwrite the current value assigned to a tag
        if one exists.

        """
        self.__tags[tag] = value

    def record_timing(self, duration, *path):
        """
        Record a timing.

        :param float duration: timing to record in seconds
        :param path: elements of the metric path to record

        A timing is a named duration value.

        """
        self.__metrics.append('{}={}'.format(
            self.application.influxdb.escape_str('.'.join(path)), duration))

    def increase_counter(self, *path, **kwargs):
        """
        Increase a counter.

        :param path: elements of the path to record
        :keyword int amount: value to record.  If omitted, the counter
            value is one.

        Counters are simply values that are summed in a query.

        """
        self.__metrics.append('{}={}'.format(
            self.application.influxdb.escape_str('.'.join(path)),
            kwargs.get('amount', 1)))

    @contextlib.contextmanager
    def execution_timer(self, *path):
        """
        Record the time it takes to run an arbitrary code block.

        :param path: elements of the metric path to record

        This method returns a context manager that records the amount
        of time spent inside of the context and records a value
        named `path` using (:meth:`record_timing`).

        """
        start = time.time()
        try:
            yield
        finally:
            self.record_timing(max(time.time(), start) - start, *path)

    def on_finish(self):
        super(InfluxDBMixin, self).on_finish()
        self.set_metric_tag('status_code', self._status_code)
        self.record_timing(self.request.request_time(), 'duration')
        self.application.influxdb.submit(
            self.settings[SETTINGS_KEY]['measurement'],
            self.__tags,
            self.__metrics)


class InfluxDBCollector(object):
    """Collects and submits stats to InfluxDB on a periodic callback.

    :param str url: The InfluxDB API URL
    :param str database: the database to write measurements into
    :param tornado.ioloop.IOLoop: the IOLoop to spawn callbacks on.
        If this parameter is :data:`None`, then the active IOLoop,
        as determined by :meth:`tornado.ioloop.IOLoop.instance`,
        is used.
    :param int submission_interval: How often to submit metric batches in
        milliseconds. Default: ``5000``
    :param max_batch_size: The number of measurements to be submitted in a
        single HTTP request. Default: ``1000``
    :param dict tags: Default tags that are to be submitted with each metric.
    :param str auth_username: Optional username for authenticated requests.
    :param str auth_password: Optional password for authenticated requests.

    This class should be constructed using the
    :meth:`~sprockets.mixins.influxdb.install` method. When installed, it is
    attached to the :class:`~tornado.web.Application` instance for your web
    application and schedules a periodic callback to submit metrics to InfluxDB
    in batches.

    """
    SUBMISSION_INTERVAL = 5000
    MAX_BATCH_SIZE = 1000
    WARN_THRESHOLD = 25000

    def __init__(self, url='http://localhost:8086', database='sprockets',
                 io_loop=None, submission_interval=SUBMISSION_INTERVAL,
                 max_batch_size=MAX_BATCH_SIZE, tags=None,
                 auth_username=None, auth_password=None):
        self._buffer = list()
        self._database = database
        self._influxdb_url = '{}?db={}'.format(url, database)
        self._interval = submission_interval or self.SUBMISSION_INTERVAL
        self._io_loop = io_loop or ioloop.IOLoop.current()
        self._max_batch_size = max_batch_size or self.MAX_BATCH_SIZE
        self._pending = 0
        self._tags = tags or {}

        # Configure the default
        defaults = {'user_agent': _USER_AGENT}
        if auth_username and auth_password:
            LOGGER.debug('Adding authentication info to defaults (%s)',
                         auth_username)
            defaults['auth_username'] = auth_username
            defaults['auth_password'] = auth_password

        self._client = httpclient.AsyncHTTPClient(force_instance=True,
                                                  defaults=defaults,
                                                  io_loop=self._io_loop)

        # Add the periodic callback for submitting metrics
        LOGGER.info('Starting PeriodicCallback for writing InfluxDB metrics')
        self._callback = ioloop.PeriodicCallback(self._write_metrics,
                                                 self._interval)
        self._callback.start()

    @staticmethod
    def escape_str(value):
        """Escape the value with InfluxDB's wonderful escaping logic:

        "Measurement names, tag keys, and tag values must escape any spaces or
        commas using a backslash (\). For example: \ and \,. All tag values are
        stored as strings and should not be surrounded in quotes."

        :param str value: The value to be escaped
        :rtype: str

        """
        return str(value).replace(' ', '\ ').replace(',', '\,')

    @property
    def database(self):
        """Return the configured database name.

        :rtype: str

        """
        return self._database

    def shutdown(self):
        """Invoke on shutdown of your application to stop the periodic
        callbacks and flush any remaining metrics.

        Returns a future that is complete when all pending metrics have been
        submitted.

        :rtype: :class:`~tornado.concurrent.TracebackFuture()`

        """
        future = concurrent.TracebackFuture()
        self._callback.stop()
        self._write_metrics()
        self._shutdown_wait(future)
        return future

    def submit(self, measurement, tags, values):
        """Add a measurement to the buffer that will be submitted to InfluxDB
        on the next periodic callback for writing metrics.

        :param str measurement: The measurement name
        :param dict tags: The measurement tags
        :param list values: The recorded measurements

        """
        self._buffer.append('{},{} {} {:d}'.format(
            self.escape_str(measurement),
            self._get_tag_string(tags),
            ','.join(values),
            int(time.time() * 1000000000)))
        if len(self._buffer) > self.WARN_THRESHOLD:
            LOGGER.warning('InfluxDB metric buffer is > %i (%i)',
                           self.WARN_THRESHOLD, len(self._buffer))

    def _get_tag_string(self, tags):
        """Return the tags to be submitted with a measurement combining the
        default tags that were passed in when constructing the class along
        with any measurement specific tags passed into the
        :meth:`~InfluxDBConnection.submit` method. Tags will be properly
        escaped and formatted for submission.

        :param dict tags: Measurement specific tags
        :rtype: str

        """
        values = dict(self._tags)
        values.update(tags)
        return ','.join(['{}={}'.format(self.escape_str(k), self.escape_str(v))
                         for k, v in values.items()])

    def _on_write_response(self, response):
        """This is invoked by the Tornado IOLoop when the HTTP request to
        InfluxDB has returned with a result.

        :param response: The response from InfluxDB
        :type response: :class:`~tornado.httpclient.HTTPResponse`

        """
        self._pending -= 1
        LOGGER.debug('InfluxDB batch response: %s', response.code)
        if response.error:
            LOGGER.error('InfluxDB batch submission error: %s', response.error)

    def _shutdown_wait(self, future):
        """Pause briefly allowing any pending metric writes to complete before
        shutting down.

        :param future tornado.concurrent.TracebackFuture: The future to resulve
            when the shutdown is complete.

        """
        if not self._pending:
            future.set_result(True)
            return
        LOGGER.debug('Waiting for pending metric writes')
        self._io_loop.add_timeout(self._io_loop.time() + 0.1,
                                  self._shutdown_wait,
                                  (future,))

    def _write_metrics(self):
        """Submit the metrics in the buffer to InfluxDB. This is invoked
        by the periodic callback scheduled when the class is created.

        It will submit batches until the buffer is empty.

        """
        if not self._buffer:
            return
        LOGGER.debug('InfluxDB buffer has %i items', len(self._buffer))
        while self._buffer:
            body = '\n'.join(self._buffer[:self._max_batch_size])
            self._buffer = self._buffer[self._max_batch_size:]
            self._pending += 1
            self._client.fetch(self._influxdb_url, method='POST',
                               body=body.encode('utf-8'),
                               raise_error=False,
                               callback=self._on_write_response)
        LOGGER.debug('Submitted all InfluxDB metrics for writing')


def install(application, **kwargs):
    """Call this to install the InfluxDB collector into a Tornado application.

    :param tornado.web.Application application: the application to
        install the collector into.
    :param kwargs: keyword parameters to pass to the
        :class:`InfluxDBCollector` initializer.
    :returns: :data:`True` if the client was installed by this call
        and :data:`False` otherwise.


    Optional configuration values:

    - **url** The InfluxDB API URL. If URL is not specified, the
        ``INFLUX_HOST`` and ``INFLUX_PORT`` environment variables will be used
        to construct the URL to pass into the :class:`InfluxDBCollector`.
    - **database** the database to write measurements into.
        The default is ``sprockets``.
    - **io_loop** A :class:`~tornado.ioloop.IOLoop` to use
    - **submission_interval** How often to submit metric batches in
        milliseconds. Default: ``5000``
    - **max_batch_size** The number of measurements to be submitted in a
        single HTTP request. Default: ``1000``
    - **tags** Default tags that are to be submitted with each metric.
    - **auth_username** A username to use for InfluxDB authentication
    - **auth_password** A password to use for InfluxDB authentication

    If ``auth_password`` is specified as an environment variable, it will be
    masked in the Python process.

    """
    if getattr(application, 'influxdb', None) is not None:
        LOGGER.warning('InfluxDBCollector is already installed')
        return False

    # Get config values
    url = '{}://{}:{}/write'.format(os.environ.get('INFLUX_SCHEME', 'http'),
                                    os.environ.get('INFLUX_HOST', 'localhost'),
                                    os.environ.get('INFLUX_PORT', 8086))
    kwargs.setdefault('url', url)

    # Build the full tag dict and replace what was passed in
    tags = {'hostname': socket.gethostname()}
    if os.environ.get('ENVIRONMENT'):
        tags['environment'] = os.environ.get('ENVIRONMENT')
    if os.environ.get('SERVICE'):
        tags['service'] = os.environ.get('SERVICE')
    tags.update(kwargs.get('tags', {}))
    kwargs['tags'] = tags

    # Check if auth variables are set as env vars and set them if so
    if os.environ.get('INFLUX_USER'):
        kwargs.setdefault('auth_username', os.environ.get('INFLUX_USER'))
        kwargs.setdefault('auth_password',
                          os.environ.get('INFLUX_PASSWORD', ''))

    # Don't leave the environment variable out there with the password
    if os.environ.get('INFLUX_PASSWORD'):
        os.environ['INFLUX_PASSWORD'] = 'X' * len(kwargs['auth_password'])

    # Create and start the collector
    setattr(application, 'influxdb', InfluxDBCollector(**kwargs))
    return True


def shutdown(application):
    """Invoke to shutdown the InfluxDB collector, writing any pending
    measurements to InfluxDB before stopping.

    :param tornado.web.Application application: the application to
        install the collector into.
    :rtype: tornado.concurrent.TracebackFuture or None

    """
    collector = getattr(application, 'influxdb', None)
    if collector:
        return collector.shutdown()
