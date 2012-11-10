import os
import re
import logging

from systools.network.ftp import Ftp

from transfer.utils.utils import parse_uri


logger = logging.getLogger(__name__)


class FtpError(Exception): pass


class FtpTransfer(object):

    _callback = None

    def __init__(self):
        self.name = None
        self.transferred = 0
        self.last_callback = 0

    def _get_client(self, info):
        if not info['host'] or not info['username']:
            return
        try:
            return Ftp(info['host'],
                    info['username'], info['password'], info.get('port', 21))
        except Exception, e:
            raise FtpError('failed to connect to host %s: %s' % (info['host'], str(e)))

    def _get_sync_info(self, src, dst):
        self.src = parse_uri(src)
        self.dst = parse_uri(dst)
        self.src_host = self._get_client(self.src)
        self.dst_host = self._get_client(self.dst)

        if self.src_host and self.dst_host:
            raise FtpError('source and destination can\'t be both remote')
        if not self.src_host and not self.dst_host:
            raise FtpError('source and destination can\'t be both local')

    def _exists(self, client, path):
        if not client:
            return os.path.exists(path)
        else:
            return client.exists(path)

    def _walk_local(self, path, topdown=True):
        if os.path.isfile(path):
            yield 'file', path
        else:
            if topdown:
                yield 'dir', path
            for root, dirs, files in os.walk(path, topdown=topdown):
                for file in files:
                    file = os.path.join(root, file)
                    yield 'file', file
                for dir in dirs:
                    dir = os.path.join(root, dir)
                    yield 'dir', dir
            if not topdown:
                yield 'dir', path

    def _walk(self, client, path, topdown=True):
        if not client:
            return self._walk_local(path, topdown)
        else:
            return client.walk(path, topdown=topdown)

    def _makedirs(self, client, path):
        if not client:
            if not os.path.exists(path):
                os.makedirs(path)
        else:
            client.cwd(path, makedirs=True)

    def _validate_src(self, file, include, exclude):
        for re_ in include:
            if not re_.search(file):
                return False
        for re_ in exclude:
            if re_.search(file):
                return False
        return True

    def _save(self, src, dst):
        if self.dst_host:
            self.dst_host.upload(src, dst)
        else:
            self.src_host.download(src, dst)

    def _delete(self, client, path, files):
        if client:
            callables = {'file': client.ftp.delete, 'dir': client.ftp.rmd}
        else:
            callables = {'file': os.remove, 'dir': os.rmdir}

        for type, file in self._walk(client, path, topdown=False):
            if file not in files[type]:
                try:
                    callables[type](file)
                except Exception, e:
                    logger.debug('failed to remove %s: %s' % (file, str(e)))

    def _get_filters(self, filters):
        if not filters:
            return []
        return [re.compile(f) for f in filters]

    # TODO: handle transferred and callback
    def _sync(self, src, dst, include=None, exclude=None, delete=False):
        self._get_sync_info(src, dst)
        src = self.src['path'].rstrip('/')
        dst = self.dst['path'].rstrip('/')
        if not self._exists(self.src_host, src):
            raise FtpError('source %s does not exist' % src)
        self._makedirs(self.dst_host, dst)

        include = self._get_filters(include)
        exclude = self._get_filters(exclude)

        re_base = re.compile(r'^%s/(.*)$' % re.escape(os.path.dirname(src)))
        dst_list = {'file': [], 'dir': []}
        for type, file in self._walk(self.src_host, src):
            self.name = file
            file_ = re_base.findall(file)[0]
            if not self._validate_src(file_, include, exclude):
                continue

            dst_file = os.path.join(dst, file_)
            dst_list[type].append(dst_file)
            if type == 'dir':
                self._makedirs(self.dst_host, dst_file)
            elif type == 'file':
                self._save(file, dst_file)

        if delete:
            base = os.path.join(dst, os.path.basename(src))
            self._delete(self.dst_host, base, dst_list)
        return True

    def process(self, src, dst, include=None, exclude=None, delete=False):
        if not isinstance(src, (list, tuple)):
            src = [src]
        for src_ in src:
            self._sync(src_, dst, include=include, exclude=exclude,
                    delete=delete)
        return True
