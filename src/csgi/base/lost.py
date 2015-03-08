import gevent
import inspect


class LazyResource(object):
    """
    @todo: Is it really needed? it breaks object discovering in IDE
    """
    
    def __init__(self, module, *args, **kwargs):
        self.module = module
        self.loaded = {}
        self.args = args
        self.kwargs = kwargs

        if hasattr(module, 'init'):
            module.init(*args, **kwargs)

    def __getattr__(self, name):
        if not name in self.loaded:
            try:
                __import__('%s.%s' % (self.module.__name__, name))
                value = LazyResource \
                    ( getattr(self.module, name)
                    , *self.args, **self.kwargs
                    )

            except ImportError:
                if not hasattr(self.module, name):
                    raise # @todo: raise what ?
                value = getattr(self.module, name)
            if inspect.isclass(value):
                value = value(*self.args, **self.kwargs)

            self.loaded[name] = value

        return self.loaded[name]


class Bundle(object):

    def __init__(self, *servers):
        self.servers = servers

    def start(self):
        jobs = []
        for server in self.servers:
            jobs.append(gevent.spawn(server.start))
        gevent.joinall(jobs)

    def stop(self):
        for server in self.servers:
            server.stop()


class ArgRouter(object):
    def __init__(self, *handler):
        self.handler = {}
        handler = list(handler)
        lastValue = handler.pop(0)

        i = 0
        while handler:
            value = handler.pop(0)
            if i % 2 == 0:
                self.handler[lastValue] = value
            lastValue = value
            i += 1

    def __call__(self, env, read, write):
        for data in read():
            args, kwargs = data
            args = list(args)
            path = args.pop(0)

            rpc_env = env.get('rpc', None)
            if rpc_env is None:
                env['rpc'] = {'path': path}
            else:
                env['rpc']['path'] = path

            self.handler[path](env, lambda: (( args, kwargs ),), write)