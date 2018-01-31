.. :changelog:

Release History
===============

`3.0.4`_ (31-Jan-2018)
----------------------
- Loosen Tornado pin to include 4.4.


`3.0.3`_ (24-Mar-2017)
----------------------
- Fix retrival of status code.

`3.0.2`_ (12-Dec-2016)
----------------------
- Fix influxdb test that fails intermittently.

`3.0.1`_ (12-Dec-2016)
----------------------
- Add README.rst to MANIFEST.in

`3.0.0`_ (12-Dec-2016)
----------------------
- Add install usage pattern for using mixin within Tornado app
- Strip down statsd mixin adding a collector class to do metric recording
- Add path prefix for the metric type, eg. counters, timers, etc
- Add configuration parameters to enable/disable metric type prefix

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

.. _Next Release: https://github.com/sprockets/sprockets.mixins.metrics/compare/3.0.4...master
.. _3.0.4: https://github.com/sprockets/sprockets.mixins.metrics/compare/3.0.3...3.0.4
.. _3.0.3: https://github.com/sprockets/sprockets.mixins.metrics/compare/3.0.2...3.0.3
.. _3.0.2: https://github.com/sprockets/sprockets.mixins.metrics/compare/3.0.1...3.0.2
.. _3.0.1: https://github.com/sprockets/sprockets.mixins.metrics/compare/3.0.0...3.0.1
.. _3.0.0: https://github.com/sprockets/sprockets.mixins.metrics/compare/2.1.1...3.0.0
.. _2.1.1: https://github.com/sprockets/sprockets.mixins.metrics/compare/2.1.0...2.1.1
.. _2.1.0: https://github.com/sprockets/sprockets.mixins.metrics/compare/2.0.1...2.1.0
.. _2.0.1: https://github.com/sprockets/sprockets.mixins.metrics/compare/2.0.0...2.0.1
.. _2.0.0: https://github.com/sprockets/sprockets.mixins.metrics/compare/1.1.1...2.0.0
.. _1.1.1: https://github.com/sprockets/sprockets.mixins.metrics/compare/1.1.0...1.1.1
.. _1.1.0: https://github.com/sprockets/sprockets.mixins.metrics/compare/1.0.1...1.1.0
.. _1.0.1: https://github.com/sprockets/sprockets.mixins.metrics/compare/1.0.0...1.0.1
.. _1.0.0: https://github.com/sprockets/sprockets.mixins.metrics/compare/0.9.0...1.0.0
.. _0.9.0: https://github.com/sprockets/sprockets.mixins.metrics/compare/0.0.0...0.9.0
