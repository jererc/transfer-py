import os
import re
from datetime import datetime
import logging

from systools.network.ssh import Host
from systools.network import get_ip

from transfer.utils.utils import parse_uri


MTIME_TOLERANCE = 3

logger = logging.getLogger(__name__)


class SftpError(Exception): pass


class SftpTransfer(object):

    _callback = None

    def __init__(self):
        self.name = None
        self.transferred = 0
        self.last_callback = 0

    def _get_client(self, info):
        if not info['host'] or not info['username']:
            return
        try:
            client = Host(info['host'], info['username'],
                    info['password'], info.get('port', 22))
        except Exception, e:
            raise SftpError('failed to connect to host %s: %s' % (info['host'], str(e)))
        return client

    def _get_sync_info(self, src, dst):
        self.src = parse_uri(src)
        self.dst = parse_uri(dst)
        self.src_host = self._get_client(self.src)
        self.dst_host = self._get_client(self.dst)

        local_ips = get_ip()
        if self.src_host and self.src['host'] in local_ips:
            self.src_host = None
        if self.dst_host and self.dst['host'] in local_ips:
            self.dst_host = None
        if self.src_host and self.dst_host:
            raise SftpError('source and destination can\'t be both remote')
        if not self.src_host and not self.dst_host:
            raise SftpError('source and destination can\'t be both local')

    def _exists(self, client, path):
        if not client:
            return os.path.exists(path)
        else:
            return client.exists(path)

    def _isfile(self, client, path):
        if not client:
            return os.path.isfile(path)
        else:
            return client.isfile(path)

    def _walk_local(self, path, topdown=True):
        if os.path.isfile(path):
            yield 'file', path, os.stat(path)
        else:
            if topdown:
                yield 'dir', path, os.stat(path)
            for root, dirs, files in os.walk(path, topdown=topdown):
                for file in files:
                    file = os.path.join(root, file)
                    yield 'file', file, os.stat(file)
                for dir in dirs:
                    dir = os.path.join(root, dir)
                    yield 'dir', dir, os.stat(dir)
            if not topdown:
                yield 'dir', path, os.stat(path)

    def _walk_remote(self, client, path, topdown=True):
        if client.isfile(path):
            yield 'file', path, client.sftp.lstat(path)
        else:
            if topdown:
                yield 'dir', path, client.sftp.lstat(path)
            for path_ in client.listdir(path):
                for res in self._walk_remote(client, path_, topdown=topdown):
                    yield res
            if not topdown:
                yield 'dir', path, client.sftp.lstat(path)

    def _walk(self, client, path, topdown=True):
        if not client:
            return self._walk_local(path, topdown)
        else:
            return self._walk_remote(client, path, topdown)

    def _makedirs(self, client, path):
        if not client:
            if not os.path.exists(path):
                os.makedirs(path)
        else:
            client.makedirs(path)

    def _validate_src(self, file, include, exclude):
        for re_ in include:
            if not re_.search(file):
                return False
        for re_ in exclude:
            if re_.search(file):
                return False
        return True

    def _validate_dst(self, client, file, src_stat):
        if not client:
            if not os.path.exists(file):
                return
            dst_stat = os.stat(file)
        else:
            try:
                dst_stat = client.sftp.lstat(file)
            except IOError:
                return

        if abs(dst_stat.st_mtime - src_stat.st_mtime) > MTIME_TOLERANCE:
            logger.debug('%s modified time mismatch (src: %s, dst: %s)' % (file,
                    datetime.utcfromtimestamp(src_stat.st_mtime), datetime.utcfromtimestamp(dst_stat.st_mtime)))
            return
        if dst_stat.st_size != src_stat.st_size:
            return
        return True

    def _save(self, src, dst, src_stat):
        if self.dst_host:
            self.dst_host.upload(src, dst, callback=self._callback)
            self.dst_host.sftp.utime(dst, (int(src_stat.st_atime), int(src_stat.st_mtime)))
        else:
            self.src_host.download(src, dst, callback=self._callback)
            os.utime(dst, (int(src_stat.st_atime), int(src_stat.st_mtime)))

    def _delete(self, client, path, files):
        if client:
            callables = {'file': client.sftp.remove, 'dir': client.sftp.rmdir}
        else:
            callables = {'file': os.remove, 'dir': os.rmdir}

        for type, file, stat in self._walk(client, path, topdown=False):
            if file not in files[type]:
                try:
                    callables[type](file)
                except Exception, e:
                    logger.debug('failed to remove %s: %s' % (file, str(e)))

    def _get_filters(self, filters):
        if not filters:
            return []
        return [re.compile(f) for f in filters]

    def _sync(self, src, dst, include=None, exclude=None, delete=False):
        self._get_sync_info(src, dst)
        src = self.src['path'].rstrip('/')
        dst = self.dst['path'].rstrip('/')
        if not self._exists(self.src_host, src):
            raise SftpError('source %s does not exist' % src)
        self._makedirs(self.dst_host, dst)

        include = self._get_filters(include)
        exclude = self._get_filters(exclude)

        re_base = re.compile(r'^%s/(.*)$' % re.escape(os.path.dirname(src)))
        dst_list = {'file': [], 'dir': []}
        for type, file, stat in self._walk(self.src_host, src):
            self.name = file
            file_ = re_base.findall(file)[0]
            if not self._validate_src(file_, include, exclude):
                continue

            dst_file = os.path.join(dst, file_)
            dst_list[type].append(dst_file)
            if type == 'dir':
                self._makedirs(self.dst_host, dst_file)
            elif type == 'file':
                if not self._validate_dst(self.dst_host, dst_file, stat):
                    self._save(file, dst_file, stat)
            self.transferred += stat.st_size

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
