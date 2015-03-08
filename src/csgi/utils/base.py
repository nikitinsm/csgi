import re


__all__ = \
    ( 'Undefined'
    , 'deepcopydict'
    , 'parse_socket_address'
    )


class Undefined(object):
    pass


def deepcopydict(org):
    """
    Fastes way to copy dict with a simple types
    """
    out = org.copy()
    for k, v in org.iteritems():
        if isinstance(v, dict):
            out[k] = deepcopydict(v)
        elif isinstance(v, list):
            out[k] = v[:]

    return out


HOST_TCP_RE = re.compile(r'^(tcp):\/\/([a-z\.]+|([0-9]+\.){3}[0-9]+):([0-9]+)$', re.I)
HOST_IPC_RE = re.compile(r'^(ipc):\/\/(.*)$', re.I)


def parse_socket_address(address):
    port = None
    m = HOST_TCP_RE.match(address)
    if m:
        protocol, host, waste, port = m.groups()
        port = int(port)
    else:
        m = HOST_IPC_RE.match(address)
        if not m:
            raise SyntaxError('%s is not a valid address ( (tcp://host[:port]|ipc://file) is required )' % address)
        protocol, host = m.groups()

    return protocol.lower(), host, port