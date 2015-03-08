import os
import logging

from gevent import socket, spawn, sleep
from gevent import Timeout
from gevent.event import AsyncResult, Event

from .utils import parse_socket_address, cached_property


__all__ = \
    ( 'Connect'
    , 'Connection'
    , 'Listen'
    , 'Socket'
    )


log = logging.getLogger(__name__)


class Socket(object):
    """
    @todo: move user, group into ipc address query string
    """
    
    def __init__(self, address, user=None, backlog=255):
        self.listeningsock = None
        self.address = address
        self.backlog = backlog
        self.user = user
        self.connections = set()

        self.protocol, self.host, self.port = parse_socket_address(self.address)

        if self.protocol not in ('ipc', 'tcp'):
            raise SyntaxError('Protocol %s not supported' % self.protocol)

        if self.protocol == 'ipc':
            self.host = os.path.abspath(self.host)
            self.address = '%s://%s' % (self.protocol, self.host)

    def connect(self):
        if self.protocol == 'ipc':
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self.host)
            return Connection(s)
        return None

    def accept(self):

        if self.protocol == 'ipc':
            try:
                os.remove(self.host)
            except OSError:
                pass

            # s.bind(self.host)

            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.bind(self.host)
            os.chmod(self.host, 0770)
            if self.user:
                import pwd

                pe = pwd.getpwnam(self.user)
                os.chown(self.host, pe.pw_uid, pe.pw_gid)
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))

        s.listen(self.backlog)

        self.listeningsock = s

        #log.info("Listening on %s (%s) ..." % (self.address, self))
        # print "Listening on %s (%s) ..." % (self.address, self)
        exec_count = 0

        while True:
            try:
                connection, addr = self.listeningsock.accept()
                connection = Connection(socket.socket(_sock=connection), self._remove_connection)
                self.connections.add(connection)
                yield connection, addr
            except Exception as e:
                if not self.listeningsock:
                    break
                #log.exception('Could not accept a connection...')
                # print 'Could not accept a connection...'
                # print traceback.print_exc()
                sleep(0.5 * exec_count)
                exec_count += 1
            else:
                #log.debug("New connection at %s" % self.address)
                # print "New connection at %s" % self.address
                exec_count = 0

    def close(self):
        if self.listeningsock:
            for connection in list(self.connections):
                connection.close()

            s = self.listeningsock
            self.listeningsock = None
            s._sock.close()
            s.close()

            if self.protocol == 'ipc':
                try:
                    os.remove(self.host)
                except OSError as e:
                    raise e

    def _remove_connection(self, connection):
        self.connections.remove(connection)


class Connection(object):
    
    _has_wfile = False
    _has_rfile = False

    timeout_read = 1

    def __init__(self, gsocket, close_callback=lambda me: None):
        self._sock = gsocket

        self.flush = self.wfile.flush
        self.write = self.wfile.write
        self.read = self.rfile.read

        self.close_callback = close_callback
        
    def __str__(self):
        socket_name = self._sock.getsockname()
        if type(socket_name) is tuple:
            socket_name = ':'.join(map(str, socket_name))

        peer_name = self._sock.getpeername()
        if type(peer_name) is tuple:
            peer_name = ':'.join(map(str, peer_name))
        return 'Connection at %s from %s' % (socket_name, peer_name)

    @cached_property
    def rfile(self):
        self._has_rfile = True
        return self._sock.makefile('rb', -1)

    @cached_property
    def wfile(self):
        self._has_wfile = True
        return self._sock.makefile('wb', 0)

    def readline(self, limit=16384):
        """
        somehow, the file-like obj does not release read locks on clients
        when connection was closed locally, so just interrupt it frequently
        which is still much faster than concatenating
        """
        while not self.rfile.closed:
            try:
                with Timeout(self.timeout_read):
                    return self.rfile.readline(limit)
            except Exception as e:
                print 'ERROR!!!', type(e), e
                pass
                # @todo: handle error
                #raise e
        return ''

    def __iter__(self):
        return self.rfile.__iter__()

    def readlines(self, hint=None):
        self.readlines = self.rfile.readlines
        return self.readlines(hint)

    def close(self):
        if self._has_rfile:
            try:
                self.rfile.close()
            except socket.error as e:
                raise e
        if self._has_wfile:
            try:
                self.wfile.close()
            except socket.error as e:
                raise e

        self._sock.shutdown(socket.SHUT_RDWR)
        self._sock._sock.close()
        self._sock.close()

        self.close_callback(self)


class Connect(object):
    def __init__(self, socket, handler, create_env=lambda: {}):
        self.socket = socket
        self.handler = handler
        self.create_env = create_env
        self.connections = set()  # @todo: the actual pool

    def __call__(self, *args, **kwargs):
        _socket = self.socket.connect()
        env = self.create_env()
        env.update\
            ( { 'socket': self.socket
              , 'connection': _socket
              , 'localclient': {'args': args, 'kwargs': kwargs, 'result': AsyncResult()}
            } )

        spawn\
            ( self.handler
            , env
            , _socket
            )

        return env['localclient']['result'].get()


class Listen(object):
    def __init__(self, socket, handler, create_env=None):
        self.socket = socket
        self.handler = handler
        if not create_env:
            create_env = lambda: {}
        self.create_env = create_env
        self._disconnected = None

    def start(self):
        self._disconnected = Event()
        self.connected = True
        for connection, address in self.socket.accept():
            spawn(self._handle_connection, connection, address)

    def _handle_connection(self, connection, address):
        try:
            env = self.create_env()
            env.update \
                ( remoteclient={'address': address}
                , socket=self.socket
                , connection=connection
                )
            self.handler(env, connection)
        except Exception as e:
            print 'ERROR!!!', type(e), e
            pass
            #raise e
            # if not isinstance(e, socket.error) or e.errno != 32:
            #     #log.exception('Could not handle connection at %s from %s' % (self.socket, address ))
            #     # print 'Could not handle connection at %s from %s' % (self.socket, address )
            # else:
            #     #log.debug('Remote client lost.')
            #     # print 'Remote client lost.'
        finally:
            connection.close()

    def stop(self):
        if not self.connected:
            return
        #log.info('Stop listening at %s (%s)' % (self.socket.address, self))
        # print 'Stop listening at %s (%s)' % (self.socket.address, self)
        self.socket.close()

        self._disconnected.set()
        self.connected = False

    def wait_for_disconnect(self):
        return self._disconnected.wait()