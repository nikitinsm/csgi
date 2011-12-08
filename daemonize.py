from lockfile.pidlockfile import PIDLockFile
from daemon import DaemonContext as _DaemonContext

import gevent

import sys,os, signal

class DaemonContext( _DaemonContext ):
    def __init__( self, pidfile, **kwargs ):

        argv = list(sys.argv)
        filename = os.path.abspath( argv.pop(0) )
        path = os.path.dirname(filename)

        if isinstance( pidfile, basestring ):
            if pidfile[0] != '/':
                pidfile = '%s/pidfile' % path

            pidfile = PIDLockFile( '%s/pid' % path )

        if argv:
            cmd = argv.pop(0)
            if cmd=='stop':
                os.kill( pidfile.read_pid(), signal.SIGTERM )
                sys.exit(0)
            if cmd=='restart':
                os.kill( pidfile.read_pid(), signal.SIGTERM )
                c = 10
                while pidfile.is_locked():
                    c-=1
                    gevent.sleep(1)
                    if not c:
                        raise Exception('Cannot stop daemon (Timed out)')

                # should just work without this - but it does not :/
                cmd = (sys.executable, filename, '&')
                os.system( ' '.join(cmd) )
                exit(0)

        if pidfile.is_locked():
            sys.stderr.write( 'Daemon seems to be already running\r\n' )
            sys.exit(-1)

        self.exit_hooks = kwargs.get('exit_hooks',[])
        files_preserve = []
        for logger in kwargs.pop('loggers',()):
            for handler in logger.handlers:
                files_preserve.append( handler.stream )

        self.loggers = []
        _DaemonContext.__init__( self, pidfile=pidfile, files_preserve=files_preserve, **kwargs )

    def open( self ):
        self.files_preserve =\
            list( tuple(self.files_preserve) + tuple( logger.handler.stream for logger in self.loggers ) )
        _DaemonContext.open( self )
        gevent.reinit()
        gevent.signal(signal.SIGTERM, self.run_exit_hooks, signal.SIGTERM, None )

    def run_exit_hooks( self, signal, frame ):
        for hook in self.exit_hooks:
            hook()
