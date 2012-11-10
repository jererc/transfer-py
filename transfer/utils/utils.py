from urlparse import urlparse
import tempfile
import shutil
from contextlib import contextmanager


class UriError(Exception): pass


def get_transfer_type(src, dst):
    schemes = []
    for uri in (src, dst):
        scheme = urlparse(uri).scheme
        if scheme:
            schemes.append(scheme)
    schemes = list(set(schemes))
    if len(schemes) != 1:
        return

    if schemes[0] == 'magnet':
        type = 'torrent'
    elif schemes[0] == 'https':
        type = 'http'
    else:
        type = schemes[0]
    return type

def parse_uri(uri):
    parsed = urlparse(uri)
    info = {
        'scheme': parsed.scheme,
        'username': None,
        'password': None,
        'host': None,
        'path': None,
        }
    res = parsed.netloc.rsplit('@', 1)
    info['host'] = res.pop()
    if res:
        data = res[0].split(':', 1)
        info['username'] = data.pop(0)
        if data:
            info['password'] = data[0]

    data = parsed.path.split(':')
    info['path'] = data.pop(0)
    if not info['path']:
        raise UriError('missing path in "%s"' % uri)
    if data:
        try:
            info['port'] = int(data[0])
        except ValueError:
            raise UriError('failed to get port from "%s"' % uri)

    return info

@contextmanager
def mkdtemp(path):
    temp_dir = tempfile.mkdtemp(prefix='transfer_', dir=path)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)
