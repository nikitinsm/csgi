from gevent import monkey
monkey.patch_all()

from csgi import Socket, Listen, Router, env, http
from csgi.rpc import Call, JsonRpcServer


def hello_world(env, arg='World'):
    """
    request ro http://0.0.0.0:9000/ 
    with POST data{"method": "hello_world", "id": "1", "params": []}
    """
    return u'Hello {0}!'.format(arg)


api_router = Router\
    ( ('hello_world', hello_world)
    , by=env['rpc']['path']
    , each=Call(env['route']['handler'])
    )

api_server = JsonRpcServer(api_router)

url_conf = \
    ( ('/', api_server)
    , )

route = Router(*url_conf, by=env['http']['path'])
transport = http.Transport(route)

socket = Socket('tcp://0.0.0.0:9000')

server = Listen(socket, transport)


if __name__ == '__main__':
    server.start()