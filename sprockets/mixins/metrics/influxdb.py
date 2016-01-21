import contextlib
import socket
import time

from tornado import httpclient, ioloop


class InfluxDBConnection(object):
    """
    Connection to an InfluxDB instance.

    :param str write_url: the URL to send HTTP requests to
    :param str database: the database to write measurements into
    :param tornado.ioloop.IOLoop: the IOLoop to spawn callbacks on.
        If this parameter is :data:`None`, then the active IOLoop,
        as determined by :meth:`tornado.ioloop.IOLoop.instance`,
        is used.

    An instance of this class is stored in the application settings
    and used to asynchronously send measurements to InfluxDB instance.
    Each measurement is sent by spawning a context-free callback on
    the IOloop.

    """

    def __init__(self, write_url, database, io_loop=None):
        self.io_loop = ioloop.IOLoop.instance() if io_loop is None else io_loop
        self.client = httpclient.AsyncHTTPClient()
        self.write_url = '{}?db={}'.format(write_url, database)

    def submit(self, measurement, tags, values):
        body = '{},{} {} {:d}'.format(measurement, ','.join(tags),
                                      ','.join(values),
                                      int(time.time() * 1000000000))
        request = httpclient.HTTPRequest(self.write_url, method='POST',
                                         body=body.encode('utf-8'))
        ioloop.IOLoop.current().spawn_callback(self.client.fetch, request)


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
        self.__tags = {
            'host': socket.gethostname(),
            'handler': '{}.{}'.format(self.__module__,
                                      self.__class__.__name__),
            'method': self.request.method,
        }

        super(InfluxDBMixin, self).initialize()
        settings = self.settings.setdefault(self.SETTINGS_KEY, {})
        if 'db_connection' not in settings:
            settings['db_connection'] = InfluxDBConnection(
                settings['write_url'], settings['database'])
        self.__metrics = []

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
        self.__metrics.append('status_code={}'.format(self._status_code))
        self.record_timing(self.request.request_time(), 'duration')
        self.settings[self.SETTINGS_KEY]['db_connection'].submit(
            self.settings[self.SETTINGS_KEY]['measurement'],
            ('{}={}'.format(k, v) for k, v in self.__tags.items()),
            self.__metrics,
        )
