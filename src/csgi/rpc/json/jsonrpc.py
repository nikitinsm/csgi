import logging

from . import jsonrpcio


__all__ = \
    ( 'JsonRpcServer'
    , )


log = logging.getLogger(__name__)


def _on_handler_fail(env, read, write):
    write\
        ( env['rpc']['parser'].encodeError
            ( env['rpc']['failure']
            , rid=env['rpc']['rid']
            )
        )


class JsonRpcServer(object):
    def __init__(self, handler, on_handler_fail=None, loads=None, dumps=None):
        self.handler = handler
        self._nowrite = lambda data: None

        if not on_handler_fail:
            on_handler_fail = _on_handler_fail

        self.on_handler_fail = on_handler_fail
        self.parser = jsonrpcio.Parser(loads=loads, dumps=dumps)

    def __call__(self, env, read, write):
        env['rpc'] = {'type': 'jsonrpc'}
        for request in read():
            # @todo: empty requests hangs here
            success, data, parser, isBatch = self.parser.decodeRequest(request)
            env['rpc']['isBatch'] = isBatch

            if not success:
                write(data)
                continue

            if isBatch:
                i = iter(data)
                for partial in i:
                    # @todo: check i.send
                    self._call_handler(env, partial, i.send, write, parser)

                write(data.encode())
            else:
                if data['id'] is not None:
                    jsonwrite = \
                        lambda result: write\
                            ( parser.encodeResponse
                              ( {'id': data['id']
                                , 'result': result
                            } ) )
                else:
                    jsonwrite = self._nowrite

                self._call_handler(env, data, jsonwrite, write, parser)


    def _call_handler(self, env, data, jsonwrite, write, parser):
        env['rpc']['path'] = data['method']
        env['rpc']['rid'] = data['id']
        env['rpc']['version'] = data['version']

        params = data['params']
        # jsonrpc supports either args or kwargs
        if isinstance(params, dict):
            kwargs = params
            args = ()
        else:
            kwargs = {}
            args = params

        jsonread = lambda: ((args, kwargs),)
        try:
            self.handler(env, jsonread, jsonwrite)
        except Exception as e:
            log.exception('Could not handle JSON-RPC request')
            env['rpc']['failure'] = e
            env['rpc']['parser'] = parser
            self.on_handler_fail(env, jsonread, write)