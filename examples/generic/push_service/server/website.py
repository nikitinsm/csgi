from jinja2 import Environment, FileSystemLoader
import os
import lib

_path = os.path.dirname(__file__)

def _404( env, read, write ):
    env['http']['status'] = 404
    write( '<html><body>404 - Not found</body></html>' )

def _500( env, read, write ):
    env['http']['status'] = 500
    write( '<html><body>500 - Internal server error </body></html>' )

class Home(object):
    def __init__( self, dojo_url ):
        jinja_env = Environment\
            ( loader=FileSystemLoader('%s/view' % _path)
            )
        jinja_env.globals.update( { 'dojo': { 'url': dojo_url } } )
        self.jinja_env = jinja_env

    def __call__( self, env, read, write ):
        session = lib.get_session( env )
        write( self.jinja_env.get_template( 'main.html' ).render().encode('utf8') )
