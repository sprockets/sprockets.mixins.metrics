import contextlib
import socket
import time

from tornado import httpclient, ioloop


class InfluxDBConnection(object):
    """Connection to an InfluxDB instance.

    :param str write_url: the URL to send HTTP requests to
    :param str database: the database to write measurements into
    :param tornado.ioloop.IOLoop: the IOLoop to spawn callbacks on.
        If this parameter is :data:`None`, then the active IOLoop,
        as determined by :meth:`tornado.ioloop.IOLoop.instance`,
        is used.
    :param int max_buffer_time: the maximum elasped time measurements
        should remain in buffer before writing to InfluxDB.
    :param int max_buffer_length: the maximum number of measurements to
        buffer before writing to InfluxDB.

    An instance of this class is stored in the application settings
    and used to asynchronously send measurements to InfluxDB instance.
    Each measurement is sent by spawning a context-free callback on
    the IOloop.

    """

    MAX_BUFFER_TIME = 5
    MAX_BUFFER_LENGTH = 100

    def __init__(self, write_url, database, io_loop=None,
                 max_buffer_time=None, max_buffer_length=None):
        self.io_loop = ioloop.IOLoop.instance() if io_loop is None else io_loop
        self.client = httpclient.AsyncHTTPClient()
        self.write_url = '{}?db={}'.format(write_url, database)

        self._buffer = []
        if max_buffer_time is None:
            max_buffer_time = self.MAX_BUFFER_TIME
        if max_buffer_length is None:
            max_buffer_length = self.MAX_BUFFER_LENGTH
        self._max_buffer_time = float(max_buffer_time)
        self._max_buffer_length = int(max_buffer_length)
        self._last_write = self.io_loop.time()

    def submit(self, measurement, tags, values):
        """Write the data using the HTTP API

        :param str measurement: The required measurement name
        :param list tags: The measurement tags
        :param list values: The recorded measurements
        """
        body = '{},{} {} {:d}'.format(measurement, ','.join(tags),
                                      ','.join(values),
                                      int(time.time() * 1000000000))
        self._buffer.append(body)
        if self._should_write:
            self._write()

    def _write(self):
        """Write the measurement"""
        body = '\n'.join(self._buffer)
        request = httpclient.HTTPRequest(self.write_url, method='POST',
                                         body=body.encode('utf-8'))
        ioloop.IOLoop.current().spawn_callback(self.client.fetch, request)
        self._last_write = self.io_loop.time()
        del self._buffer[:]

    @property
    def _should_write(self):
        """Returns ``True`` if the buffered measurements should be sent"""
        if len(self._buffer) >= self._max_buffer_length:
            return True
        if self.io_loop.time() >= (self._last_write + self._max_buffer_time):
            return True
        return False


class InfluxDBMixin(object):
    """
    Mix this class in to record measurements to a InfluxDB server.

    **Configuration**

    :database:
        InfluxDB database to write measurements to. This is passed
        as the ``db`` query parameter when writing to Influx.

        https://docs.influxdata.com/influxdb/v0.9/guides/writing_data/

    :write_url:
        The URL that the InfluxDB write endpoint is available on.
        This is used as-is to write data into Influx.

    """

    SETTINGS_KEY = 'sprockets.mixins.metrics.influxdb'
    """``self.settings`` key that configures this mix-in."""

    def initialize(self):
        super(InfluxDBMixin, self).initialize()
        if self.SETTINGS_KEY in self.settings:
            settings = self.settings[self.SETTINGS_KEY]
            if 'db_connection' not in settings:
                settings['db_connection'] = InfluxDBConnection(
                    settings['write_url'], settings['database'],
                    max_buffer_time=settings.get('max_buffer_time'),
                    max_buffer_length=settings.get('max_buffer_length'))

        self.__metrics = []
        self.__tags = {
            'host': socket.gethostname(),
            'handler': '{}.{}'.format(self.__module__,
                                      self.__class__.__name__),
            'method': self.request.method,
        }

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
        self.__metrics.append('{}={}'.format('.'.join(path), duration))

    def increase_counter(self, *path, **kwargs):
        """
        Increase a counter.

        :param path: elements of the path to record
        :keyword int amount: value to record.  If omitted, the counter
            value is one.

        Counters are simply values that are summed in a query.

        """
        self.__metrics.append('{}={}'.format('.'.join(path),
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
            fini = max(time.time(), start)
            self.record_timing(fini - start, *path)

    def on_finish(self):
        super(InfluxDBMixin, self).on_finish()
        self.set_metric_tag('status_code', self._status_code)
        self.record_timing(self.request.request_time(), 'duration')
        self.settings[self.SETTINGS_KEY]['db_connection'].submit(
            self.settings[self.SETTINGS_KEY]['measurement'],
            ('{}={}'.format(k, v) for k, v in self.__tags.items()),
            self.__metrics,
        )
