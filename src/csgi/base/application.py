import logging

from csgi.base.exceptions import NotFound


__all__ = \
    ( 'Router'
    , 'env'
    )


log = logging.getLogger(__name__)


class Router(object):

    def __init__(self, *handlers, **params):
        self.handler = []
        self.named_routes = {}

        routes = set()

        for i in range(len(handlers)):
            (key, handler) = handlers[i]
            if key in routes:
                raise SyntaxError('Routes must be unique')

            routes.add(key)
            if isinstance(key, basestring):
                self.named_routes[key] = handler
            else:
                if hasattr(key, 'match'):
                    key = key.match
                if not callable(key):
                    raise SyntaxError(
                        'Invalid route - must be a string, callable or an object with a match() method')
                self.handler.append((key, handler ))

        self.by = params.pop('by')
        self.each = params.pop('each', None)
        self.on_not_found = params.pop\
            ( 'on_not_found'
            , lambda env, read, write: self._log_error('route not found .. env: %s' % (env,))
            )

        if params:
            raise SyntaxError('Invalid keyword arguments: %s' % params.keys())

    def __call__(self, env, read, write):
        value = self.by(env)
        print self.named_routes
        handler = self.named_routes.get(value, None)

        env['route'] = {'path': value}

        if not handler:
            for (key, handler_) in self.handler:
                match = key(value)
                if match:
                    groups = match.groupdict()
                    if groups:
                        env['route'].update(groups)

                    handler = handler_
                    break

        if not handler:
            self.on_not_found(env, read, write)
            return

        if callable(self.each):
            env['route']['handler'] = handler
            self.each(env, read, write)
        else:
            try:
                handler(env, read, write)
            except NotFound:
                self.on_not_found(env, read, write)
            except Exception as e:
                print 'ERROR!!!', type(e), e

    def _log_error(self, error):
        #print '[ERROR] ', error
        log.error(error)


class Setter(object):
    def __init__(self, path, updater, handler):
        self.path = path
        self.updater = updater
        self.handler = handler

    def __call__(self, env, r, w):
        env_to_update = env
        value = self.updater(env)

        if self.path:
            for part in self.path[:-1]:
                env_to_update = env_to_update[part]
            env_to_update[self.path[-1]] = value
        else:
            env = value

        self.handler(env, r, w)


class Env(object):

    def __call__(self, *args, **kwargs):
        env = args[0]
        value = env
        for part in self.path:
            value = value[part]
        if callable(value):
            return value(*args, **kwargs)
        else:
            return value

    def __init__(self, path=None, name=None):
        if path is None:
            self.path = ()
        else:
            self.path = path + (name,)

    def __getitem__(self, name):
        return Env(self.path, name)

    def set(self, updater, handler):
        return Setter(self.path, updater, handler)
    
    
env = Env()