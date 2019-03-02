Configuration
=============

sprockets.mixins.metrics has the ability to be configured via environment variables.

The following environment variables are recognized:

+-----------------+---------------------------------------+----------+---------------+
| Name            | Description                           | Required | Default Value |
+-----------------+---------------------------------------+----------+---------------+
| STATSD_HOST     | The StatsD host to connect to         | No       | 127.0.0.1     |
+-----------------+---------------------------------------+----------+---------------+
| STATSD_PORT     | The port on which StatsD is listening | No       | 8125          |
+-----------------+---------------------------------------+----------+---------------+
| STATSD_PROTOCOL | The transport-layer protocol to use   | No       | 8125          |
+-----------------+---------------------------------------+----------+---------------+
