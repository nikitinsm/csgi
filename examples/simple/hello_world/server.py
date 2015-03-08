from gevent import monkey
monkey.patch_all()

from csgi import Socket, Listen, Router, env, http


def hello_world(env, read, write):
    write('Hello World!')


url_conf = \
    ( ('/', hello_world)
    , )

route = Router(*url_conf, by=env['http']['path'])
transport = http.Transport(route)

socket = Socket('tcp://0.0.0.0:9000')

server = Listen(socket, transport)


if __name__ == '__main__':
    server.start()