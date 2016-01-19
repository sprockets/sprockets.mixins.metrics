import socket


class StatsdMixin(object):
    """
    Mix this class in to record metrics to a Statsd server.

    **Configuration**

    :namespace:
        Path to prefix metrics with.  If undefined, this defaults to
        ``applications`` + ``self.__class__.__module__``

    :host:
        Host name of the StatsD server to send metrics to.  If undefined,
        this defaults to ``127.0.0.1``.

    :port:
        Port number that the StatsD server is listening on.  If undefined,
        this defaults to ``8125``.

    """

    SETTINGS_KEY = 'sprockets.mixins.metrics.statsd'
    """``self.settings`` key that configures this mix-in."""

    def initialize(self):
        super(StatsdMixin, self).initialize()
        settings = self.settings.setdefault(self.SETTINGS_KEY, {})
        if 'socket' not in settings:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
            settings['socket'] = sock
        if 'namespace' not in settings:
            settings['namespace'] = 'applications.{}'.format(
                self.__class__.__module__)
        settings.setdefault('host', '127.0.0.1')
        settings.setdefault('port', '8125')
        self.__status_code = None

    def set_status(self, status_code, reason=None):
        # Extended to track status code to avoid referencing the
        # _status internal variable
        self.__status_code = status_code
        super(StatsdMixin, self).set_status(status_code, reason=reason)

    def record_timing(self, milliseconds, *path):
        """
        Record a timing.

        :param float milliseconds: millisecond timing to record
        :param path: elements of the metric path to record

        This method records a timing to the application's namespace
        followed by a calculated path.  Each element of `path` is
        converted to a string and normalized before joining the
        elements by periods.  The normalization process is little
        more than replacing periods with dashes.

        """
        settings = self.settings[self.SETTINGS_KEY]
        normalized = '.'.join(str(p).replace('.', '-') for p in path)
        msg = '{0}.{1}:{2}|ms'.format(settings['namespace'], normalized,
                                      milliseconds)
        settings['socket'].sendto(msg.encode('ascii'),
                                  (settings['host'], int(settings['port'])))

    def on_finish(self):
        """
        Records the time taken to process the request.

        This method records the number of milliseconds that were used
        to process the request (as reported by
        :meth:`tornado.web.HTTPRequest.request_time` * 1000) under the
        path defined by the class's module, it's name, the request method,
        and the status code.  The :meth:`.record_timing` method is used
        to send the metric, so the configured namespace is used as well.

        """
        super(StatsdMixin, self).on_finish()
        self.record_timing(self.request.request_time() * 1000,
                           self.__class__.__name__, self.request.method,
                           self.__status_code)
