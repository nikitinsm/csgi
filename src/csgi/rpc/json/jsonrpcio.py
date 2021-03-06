"""
@todo: replace camelCase with undescores
@todo: rename Exceptions, make more broad
@todo: decomposite
"""
import logging
import json as builtin_json
import datetime

from csgi.utils import Undefined


__all__ = \
    ( 'Parser'
    , )


__has_rfc3339__ = True
try:
    from rfc3339 import rfc3339
except ImportError:
    __has_rfc3339__ = False

__has_iso8601__ = True
try:
    import iso8601
except ImportError:
    __has_iso8601__ = False

log = logging.getLogger(__name__)

JSONRPC_VERSION_1_0 = "1.0"  # http://groups.google.com/group/json-rpc/web/json-1-0-spec
JSONRPC_VERSION_2_0 = "2.0"  # http://groups.google.com/group/json-rpc/web/json-rpc-2-0

# @todo: not supported yet
# JSONRPC_VERSION_1_1 = "1.1"   # http://groups.google.com/group/json-rpc/web/json-rpc-1-1-wd



class JSONRPC_BaseError(BaseException):
    extra = {}

    def __init__(self, message=None, code=None, extra=None, version=Undefined, rid=None):
        self.version = version

        if code is not None:
            self.code = code
        if message is not None:
            self.message = message
        if extra is not None:
            self.extra = extra
        if rid is not None:
            self.rid = rid


class JSONRPCProtocol_Error(JSONRPC_BaseError):
    code = -32603
    message = "JSON-RPC protocol error"


class JSONRPCProtocol_UnexpectedError(JSONRPCProtocol_Error):
    code = -32603
    message = "Unexpected server error"


class JSONRPCProtocol_ParseError(JSONRPCProtocol_Error):
    code = -32700
    message = "JSON-RPC parse error"


class JSONRPCProtocol_EncodeError(JSONRPCProtocol_ParseError):
    message = "Cannot encode response to JSON"


class JSONRPCProtocol_DecodeError(JSONRPCProtocol_ParseError):
    message = "Cannot decode request from JSON"


class JSONRPCProtocol_MethodNotFound(JSONRPCProtocol_Error):
    code = -32601
    message = "Method not found"


class JSONRPCProtocol_UnknownVersion(JSONRPCProtocol_Error):
    code = -32000
    message = "Unknown JSON-RPC version"


class JSONRPCProtocol_ResourceNotFound(JSONRPCProtocol_Error):
    code = -32001
    message = "Resource not found"


class JSONRPCProtocol_FeatureNotSupported(JSONRPCProtocol_Error):
    code = -32002
    message = "Feature not supported"


class JSONRPCApplication_Error(JSONRPC_BaseError):
    code = 100
    message = "Application error"
    exception = None


class JSONRPCApplication_UnexpectedError(JSONRPCApplication_Error):
    code = 999
    message = "Unexpected application error"


def defaultErrorConstructor(exceptionObj):
    extra = dict(exceptionObj.extra)
    return exceptionObj.code, exceptionObj.message, extra


class JSONDateTimeEncoder(builtin_json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            if __has_rfc3339__:
                return rfc3339(obj, utc=True, use_system_timezone=False)
            return obj.isoformat()
        else:
            return builtin_json.JSONEncoder.default(self, obj)


def datetime_decoder(d):
    if isinstance(d, list):
        pairs = enumerate(d)
    elif isinstance(d, dict):
        pairs = d.items()
    result = []
    for k, v in pairs:
        if isinstance(v, basestring):
            if __has_iso8601__:
                try:
                    v = iso8601.parse_date(v)
                except (iso8601.ParseError, TypeError):
                    pass
            else:
                try:
                    # The %f format code is only supported in Python >= 2.6.
                    # For Python <= 2.5 strip off microseconds
                    # v = datetime.datetime.strptime(v.rsplit('.', 1)[0],
                    # '%Y-%m-%dT%H:%M:%S')
                    v = datetime.datetime.strptime(v, '%Y-%m-%dT%H:%M:%S.%f')
                except ValueError:
                    try:
                        v = datetime.datetime.strptime(v, '%Y-%m-%d').date()
                    except ValueError:
                        pass
        elif isinstance(v, (dict, list)):
            v = datetime_decoder(v)
        result.append((k, v))
    if isinstance(d, list):
        return [x[1] for x in result]
    elif isinstance(d, dict):
        return dict(result)


loads = lambda text: builtin_json.loads(text, object_hook=datetime_decoder)
dumps = lambda obj: builtin_json.dumps(obj, cls=JSONDateTimeEncoder)

import types
"""
@todo: WTF? - remove looks like too ugly shit
"""
json = types.ModuleType('jsonrpcio.json')

json.loads = loads
json.dumps = dumps


class Parser(object):
    version = None

    def __init__(self, loads=None, dumps=None, errorConstructor=defaultErrorConstructor):
        if not loads:
            loads = json.loads
        if not dumps:
            dumps = json.dumps

        self.errorConstructor = errorConstructor
        self.loads = loads
        self.dumps = dumps
        if self.version is None:
            self.parsers = tuple(_Version(loads, dumps, errorConstructor) for _Version in PARSERS)

    def decodeRequest(self, body, extra=None):

        protocolError = Undefined
        result = Undefined
        if extra is None:
            extra = {}

        success = True
        isBatch = False
        parser = self.parsers[0]

        try:
            parsed = self.decode(body)
        except JSONRPCProtocol_Error as e:
            protocolError = e
        else:
            for parser in self.parsers:
                log.debug("trying %s" % parser.version)
                try:
                    (success, result, isBatch) = parser.decodeRequest \
                        (parsed
                         , extra
                        )
                    protocolError = Undefined
                    log.debug('done')
                    break
                except JSONRPCProtocol_Error as e:
                    log.debug('protocol error (%s) , trying next ...' % e.message)
                    protocolError = e
                except Exception as e:
                    log.exception('Could not decode request')
                    protocolError = JSONRPCProtocol_UnexpectedError()
                    break

        if protocolError is not Undefined:
            success = False
            result = parser.encodeError(protocolError)

        return success, result, parser, isBatch

    def encode(self, response):
        try:
            return self.dumps(response)
        except (TypeError, ValueError):
            log.exception('Cannot encode response to JSON')
            raise JSONRPCProtocol_EncodeError()

    def decode(self, body):
        try:
            return self.loads(body)
        except (TypeError, ValueError):
            log.exception('Cannot decode body %s from JSON' % (body,))
            raise JSONRPCProtocol_DecodeError()


class _1_0(Parser):
    version = JSONRPC_VERSION_1_0

    def encodeError(self, exceptionObj, **requestInfo):
        if not isinstance(exceptionObj, JSONRPC_BaseError):
            exception = exceptionObj
            exceptionObj = JSONRPCApplication_UnexpectedError()
            exceptionObj.exception = exception

        exceptionObj.version = self.version
        rid = requestInfo.pop('rid', None)

        try:
            return self.doEncodeError \
                (rid, *self.errorConstructor(exceptionObj), **requestInfo)
        except JSONRPCProtocol_EncodeError as e:
            return self.doEncodeError \
                (rid, *self.errorConstructor(e), **requestInfo)

    def doEncodeError(self, rid, code, message, extra=None):
        error = {'code': code, 'message': message}
        if isinstance(extra, dict):
            error['error'] = extra
        return self.encode({'result': None, 'id': rid, 'error': error})

    def doEncodeResponse(self, result):
        rid = result.get('id', None)
        if rid is None:  # is a notification
            return None
        return self.encode({'result': result['result'], 'id': rid, 'error': None})

    def decodeRequest(self, parsed, extra):
        """
        @todo: argument signature does not match
        """
        if not isinstance(parsed, dict):
            raise JSONRPCProtocol_ParseError("JSON root must be an Object")

        parsed = dict(parsed)
        rid = parsed.pop('id', None)
        method = parsed.pop('method', Undefined)
        params = parsed.pop('params', Undefined)

        if Undefined in (rid, method, params):
            raise JSONRPCProtocol_ParseError("Members 'id','method' and 'params' are required")

        if parsed:
            raise JSONRPCProtocol_ParseError("Too many fields received")

        # from now on we can be sure its a 1.0 request
        # so render everything as 1.0 response ( no raise )

        error = None
        if not isinstance(method, basestring):
            error = JSONRPCProtocol_ParseError("'method' must be a String", rid=rid)

        if not isinstance(params, list):
            error = JSONRPCProtocol_ParseError("'params' must be an Array", rid=rid)

        if error:
            result = self.encodeError \
                ( error
                , rid=rid
                )
        else:
            result = \
                { 'method': method
                , 'params': params
                , 'version': self.version
                , 'id': rid
                }

        return \
            ( not error
            , result
            , False
            )

    def encodeResponse(self, result):
        try:
            return self.doEncodeResponse(result)
        except JSONRPCProtocol_EncodeError as e:
            return self.encodeError\
                ( e
                , rid=result.get('id', None)
                )


class _2_0(_1_0):
    version = JSONRPC_VERSION_2_0

    class BatchResponse(object):

        def __init__(self, request, parser, extra):
            self.request = request
            self.response = []
            self.parser = parser
            self.extra = extra

        def __iter__(self):

            for request in self.request:
                try:
                    success, partial, waste = self.parser.decodeRequest(request, self.extra, True)
                except JSONRPC_BaseError as e:
                    self.response.append(self.parser.encodeError(e, rid=request.get('id'), isBatch=True))
                    continue

                rid = partial.get('id', None)
                result = yield partial

                if rid:
                    self.response.append \
                        ( { 'id': rid
                          , 'result': result
                          , 'jsonrpc': self.parser.version
                        } )

        def encode(self):
            encoded = self.parser.encode(self.response)
            return encoded

    def doEncodeError(self, rid, code, message, extra=None, isBatch=False):
        error = {'code': code, 'message': message}

        if isinstance(extra, dict):
            error['data'] = extra

        error = {'id': rid, 'error': error, 'jsonrpc': self.version}
        if isBatch:
            return error

        return self.encode(error)

    def doEncodeResponse(self, result):
        rid = result.get('id', None)
        if rid is None:
            return None

        return self.encode({'id': rid, 'result': result['result'], 'jsonrpc': self.version})

    def decodeRequest(self, parsed, extra, isBatch=False):
        error = None
        
        if isinstance(parsed, list):
            if isBatch:
                raise JSONRPCProtocol_ParseError("JSON request must be an Object")
            else:
                isBatch = True
                result = self.BatchResponse(parsed, self, extra)

        elif not isinstance(parsed, dict):
            raise JSONRPCProtocol_ParseError("JSON request must be an Object")
        else:
            parsed = dict(parsed)
            rid = parsed.pop('id', None)
            version = parsed.pop('jsonrpc', Undefined)
            method = parsed.pop('method', Undefined)
            params = parsed.pop('params', Undefined)

            if Undefined in ( method, params, version ):
                raise JSONRPCProtocol_ParseError("Members 'jsonrpc', 'method' and 'params' are required")

            if parsed:
                raise JSONRPCProtocol_ParseError("Too many fields received")

            if version != self.version:
                raise JSONRPCProtocol_UnknownVersion("Invalid JSON-RPC Version specified", extra={'version': version})

            # from now on we can be sure its a 2.0 request
            # so render everything as 2.0 response ( no raise )
            if not isinstance(method, basestring):
                error = JSONRPCProtocol_ParseError("'method' must be a String")

            if not isinstance(params, (list, dict)):
                error = JSONRPCProtocol_ParseError("'params' must be an array or dict")

            if error:
                if not isBatch:
                    result = self.encodeError\
                        ( error
                        , rid=rid
                        )
                else:
                    raise error

            else:
                result = \
                    { 'method': method
                    , 'params': params
                    , 'version': self.version
                    , 'id': rid
                    }

        return \
            ( not error
            , result
            , isBatch
            )

PARSERS = \
    ( _2_0
    , _1_0
    )