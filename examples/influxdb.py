import os
import signal

from sprockets.mixins import metrics
from tornado import gen, ioloop, web


class SimpleHandler(metrics.InfluxDBMixin, web.RequestHandler):
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

    @gen.coroutine
    def prepare(self):
        maybe_future = super(SimpleHandler, self).prepare()
        if gen.is_future(maybe_future):
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
    influx_url = 'http://{}:{}/write'.format(
        os.environ.get('INFLUX_HOST', '127.0.0.1'),
        os.environ.get('INFLUX_PORT', 8086))
    settings = {
        metrics.InfluxDBMixin.SETTINGS_KEY: {
            'measurement': 'cli',
            'database': 'testing',
            'write_url': influx_url,
        }
    }
    return web.Application([web.url('/', SimpleHandler)], **settings)


if __name__ == '__main__':
    app = make_application()
    app.listen(8000)
    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)
    ioloop.IOLoop.instance().start()
