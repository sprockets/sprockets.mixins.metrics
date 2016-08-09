.. :changelog:

Release History
===============

`2.1.1`_ (9-Aug-2016)
---------------------
- Fix InfluxDB URL creation from environment variables

`2.1.0`_ (9-Aug-2016)
---------------------
- Add authentication environment variables for InfluxDB

`2.0.1`_ (21-Mar-2016)
----------------------
- Make it possible to call methods (e.g.,
  :meth:`~sprockets.mixins.metrics.influxdb.InfluxDBMixin.set_metric_tag`)
  during the Tornado request handler initialization phase.

`2.0.0`_ (11-Mar-2016)
----------------------
- Rework InfluxDB buffering to use a periodic callback instead of flushing
  the buffer upon request.

`1.1.1`_ (9-Mar-2016)
---------------------
- Fix packaging woes part deux.

`1.1.0`_ (9-Mar-2016)
---------------------
- Update InfluxDB mixin to buffer measurements across requests based on a
  max time and/or length.

`1.0.1`_ (1-Feb-2016)
---------------------
- Fix packaging woes.

`1.0.0`_ (1-Feb-2016)
---------------------
- Remove extraneous quotes from InfluxDB tag values.
- Convert HTTP status code from value to a tag in the InfluxDB mix-in.

`0.9.0`_ (27-Jan-2016)
----------------------
- Add :class:`sprockets.mixins.metrics.StatsdMixin`
- Add :class:`sprockets.mixins.metrics.testing.FakeStatsdServer`
- Add :class:`sprockets.mixins.metrics.testing.FakeInfluxHandler`
- Add :class:`sprockets.mixins.metrics.InfluxDBMixin`
- Add :class:`sprockets.mixins.metrics.influxdb.InfluxDBConnection`

.. _Next Release: https://github.com/sprockets/sprockets.mixins.metrics/compare/2.1.1...master
.. _2.1.0: https://github.com/sprockets/sprockets.mixins.metrics/compare/2.1.0...2.1.1
.. _2.1.0: https://github.com/sprockets/sprockets.mixins.metrics/compare/2.0.1...2.1.0
.. _2.0.1: https://github.com/sprockets/sprockets.mixins.metrics/compare/2.0.0...2.0.1
.. _2.0.0: https://github.com/sprockets/sprockets.mixins.metrics/compare/1.1.1...2.0.0
.. _1.1.1: https://github.com/sprockets/sprockets.mixins.metrics/compare/1.1.0...1.1.1
.. _1.1.0: https://github.com/sprockets/sprockets.mixins.metrics/compare/1.0.1...1.1.0
.. _1.0.1: https://github.com/sprockets/sprockets.mixins.metrics/compare/1.0.0...1.0.1
.. _1.0.0: https://github.com/sprockets/sprockets.mixins.metrics/compare/0.9.0...1.0.0
.. _0.9.0: https://github.com/sprockets/sprockets.mixins.metrics/compare/0.0.0...0.9.0
