import signal

from sprockets.mixins.metrics import statsd
from tornado import concurrent, gen, ioloop, web


class SimpleHandler(statsd.StatsdMixin, web.RequestHandler):
    """
    Simply emits a timing metric around the method call.

    The metric namespace and StatsD endpoint are configured in
    the application settings object so there is nothing to do in
    a request handler.

    """

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
        yield gen.sleep(0.25)
        self.set_status(204)
        self.finish()

    def post(self):
        """Example of increasing a counter."""
        self.increase_counter('request', 'path')
        self.set_status(204)


def _sig_handler(*args_):
    iol = ioloop.IOLoop.instance()
    iol.add_callback_from_signal(iol.stop)


def make_application():
    """
    Create a application configured to send metrics.

    Metrics will be sent to localhost:8125 namespaced with
    ``webapps``. Run netcat or a similar listener then run this
    example. HTTP GETs will result in a metric like::

        webapps.SimpleHandler.GET.204:255.24497032165527|ms

    """
    settings = {}
    application = web.Application([web.url('/', SimpleHandler)], **settings)
    statsd.install(application, **{'namespace': 'testing'})
    return application


if __name__ == '__main__':
    app = make_application()
    app.listen(8000)
    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)
    ioloop.IOLoop.instance().start()
