__all__ = \
    ( 'NotFound'
    , )


class NotFound(Exception):

    def __init__(self, method, *args, **kwargs):
        self.method = method
        super(NotFound, self).__init__(*args, **kwargs)