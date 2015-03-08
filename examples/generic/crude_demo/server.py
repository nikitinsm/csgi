"""
Open in browser

http://0.0.0.0:9000/
http://0.0.0.0:9000/wsgi/simple
http://0.0.0.0:9000/wsgi/werkzeug

or play with Json Rpc 
http//0.0.0.0:9000/service/jsonrpc
http//0.0.0.0:9000/pubsub/longpoll/jsonrpc

"""
import logging
import re
import testresource

from logging import FileHandler

from csgi import Router, Call, Socket, Listen, Connect, LongPoll, Bundle, LazyResource, env, http, event, JsonRpcServer
from csgi.simple import marshal
from csgi.simple.transport import Line as LineTransport
from csgi.http import wsgi
from csgi.daemonize import DaemonContext


# logger setup
logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)

handler = FileHandler('log')
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

logger.addHandler(handler)

daemon = DaemonContext(stderr=handler.stream, pidfile='pid')

# server setup

log = logging.getLogger(__name__)


config = {'db_uri': 'sqlite:///db.sqlite'}
config['resource'] = resource = LazyResource(testresource, config)
resource.wsgi.werkzeugapp.application.Shorty.init_database()


config['workerclient'] = Connect\
    ( Socket('ipc://worker.sock')
    , LineTransport(marshal.Json(event.Client()))
    )


config['worker'] = workserver = Listen\
    ( Socket('ipc://worker.sock')
    , LineTransport(marshal.Json(event.Channel({'workerchannel': resource.Worker})))
    )


services = Router\
    ( ('service.echo', resource.EchoHandler.echo )
    , ('other.echo', resource.EchoHandler.echo )
    , by=env['rpc']['path']
    , each=Call(env['route']['handler'])
    )


channels = event.Channel\
    ( { 'service.channel': resource.EchoHandler.channel
      , 'other.channel': resource.EchoHandler.channel
    } )


jsonservice = JsonRpcServer(services)
longpoll = LongPoll(channels)


pubsub = JsonRpcServer\
    ( Router\
      ( ('connect', longpoll.connect)
      , ('next', longpoll.next)
      , ('emit', longpoll.emit)
      , by=env['rpc']['path']
    ) )


config['server'] = server = Listen\
    ( Socket('tcp://0.0.0.0:9000')
    , http.Transport\
      ( Router\
        ( ( '/', resource.http.Hello )
        , ( re.compile('^(?P<approot>\/wsgi/simple).*$'), wsgi.Server(resource.wsgi.SimpleApp))
        , ( re.compile('^(?P<approot>\/wsgi/werkzeug).*$'), wsgi.Server(resource.wsgi.werkzeugapp.application.Shorty))
        , ( '/service/jsonrpc', http.Method(POST=jsonservice) )
        , ( '/pubsub/longpoll/jsonrpc', http.Method(POST=pubsub) )
        , by=env['http']['path']
        , on_not_found=resource.http._404
        )
      , on_handler_fail=resource.http._500
    ) )


if __name__ == '__main__':
    Bundle(server, workserver).start()