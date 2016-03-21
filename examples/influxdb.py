import signal

from sprockets.mixins.metrics import influxdb
from tornado import concurrent, gen, ioloop, web


class SimpleHandler(influxdb.InfluxDBMixin, web.RequestHandler):
    """
    Simply emits a few metrics around the GET method.

    The ``InfluxDBMixin`` sends all of the metrics gathered during
    the processing of a request as a single measurement when the
    request is finished.  Each request of this sample will result
    in a single measurement using the service name as the key.

    The following tag keys are defined by default:

        handler="examples.influxdb.SimpleHandler"
        host="$HOSTNAME"
        method="GET"

    and the following values are written:

        duration=0.2573668956756592
        sleepytime=0.255108118057251
        slept=42
        status_code=204

    The duration and status_code values are handled by the mix-in
    and the slept and sleepytime values are added in the method.

    """

    def initialize(self):
        super(SimpleHandler, self).initialize()
        self.set_metric_tag('environment', 'testing')

    @gen.coroutine
    def prepare(self):
        maybe_future = super(SimpleHandler, self).prepare()
        if concurrent.is_future(maybe_future):
            yield maybe_future

        if 'Correlation-ID' in self.request.headers:
            self.set_metric_tag('correlation_id',
                                self.request.headers['Correlation-ID'])

    @gen.coroutine
    def get(self):
        with self.execution_timer('sleepytime'):
            yield gen.sleep(0.25)
            self.increase_counter('slept', amount=42)
        self.set_status(204)
        self.finish()


def _sig_handler(*args_):
    iol = ioloop.IOLoop.instance()
    iol.add_callback_from_signal(iol.stop)


def make_application():
    """
    Create a application configured to send metrics.

    Measurements will be sent to the ``testing`` database on the
    configured InfluxDB instance.  The measurement name is set
    by the ``service`` setting.

    """
    settings = {
        influxdb.SETTINGS_KEY: {
            'measurement': 'example',
        }
    }
    application = web.Application([web.url('/', SimpleHandler)], **settings)
    influxdb.install(application, **{'database': 'testing'})
    return application


if __name__ == '__main__':
    app = make_application()
    app.listen(8000)
    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)
    ioloop.IOLoop.instance().start()
