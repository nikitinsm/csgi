from gevent import monkey
monkey.patch_all()

from csgi import Socket, Listen, Router, env, http
from csgi.rpc import Call, JsonRpcServer


#
# 1. Define rpc callable
#

def hello_world(env, arg='World'):
    """
    Make request to http://0.0.0.0:9000/ with POST data:
            {"method": "hello_world", "id": "1", "params": []}
        or:
            {"method": "hello_world", "id": "1", "params": ["CSGI"]}
    """
    return u'Hello {0}!'.format(arg)


#
# 2. Configure api
#

api_url_conf = \
    ( ('hello_world', hello_world)
    , )
api_router = Router\
    ( *api_url_conf
    , by=env['rpc']['path']
    , each=Call(env['route']['handler'])
    )
api_server = JsonRpcServer(api_router)


#
# 3. Configure transport layer
#

url_conf = \
    ( ('/', api_server)
    , )

router = Router(*url_conf, by=env['http']['path'])
transport = http.Transport(router)


#
# 4. Start server
#

if __name__ == '__main__':
    Listen(Socket('tcp://0.0.0.0:9000'), transport).start()