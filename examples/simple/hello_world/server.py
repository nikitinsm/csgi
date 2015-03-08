from gevent import monkey
monkey.patch_all()

from csgi import Socket, Listen, Router, env, http


#
# 1. Define view 
#

def hello_world(env, read, write):
    write('Hello World!')


#
# 2. Configure transport layer
#

url_conf = \
    ( ('/', hello_world)
    , )

router = Router(*url_conf, by=env['http']['path'])
transport = http.Transport(router)


#
# 3. Start server
#

if __name__ == '__main__':
    Listen(Socket('tcp://0.0.0.0:9000'), transport).start()