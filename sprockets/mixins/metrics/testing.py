import socket


class FakeStatsdServer(object):
    """
    Implements something resembling a statsd server.

    :param tornado.ioloop.IOLoop iol: the loop to attach to

    Create an instance of this class in your asynchronous test case
    attached to the IOLoop and configure your application to send
    metrics to it.  The received datagrams are available in the
    ``datagrams`` attribute for validation in your tests.

    .. attribute:: sockaddr

       The socket address that the server is listening on.  This is
       a tuple returned from :meth:`socket.socket.getsockname`.

    .. attribute:: datagrams

       A list of datagrams that have been received by the server.

    """

    def __init__(self, iol):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                                    socket.IPPROTO_UDP)
        self.socket.bind(('127.0.0.1', 0))
        self.sockaddr = self.socket.getsockname()
        self.datagrams = []

        iol.add_handler(self.socket, self._handle_events, iol.READ)
        self._iol = iol

    def close(self):
        if self.socket is not None:
            if self._iol is not None:
                self._iol.remove_handler(self.socket)
                self._iol = None
            self.socket.close()
            self.socket = None

    def _handle_events(self, fd, events):
        if fd != self.socket:
            return
        if self._iol is None:
            raise RuntimeError

        if events & self._iol.READ:
            data, _ = self.socket.recvfrom(4096)
            self.datagrams.append(data)
