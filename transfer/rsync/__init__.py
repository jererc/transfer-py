import logging

from systools.network.ssh import Host

from transfer import settings, Settings
from transfer.utils.utils import parse_uri


logger = logging.getLogger(__name__)


class RsyncError(Exception): pass
class RsyncNotFound(Exception): pass


class RsyncTransfer(object):

    def __init__(self):
        self.name = None
        self.transferred = 0
        self.last_callback = 0
        self.default_args = Settings.get_settings('rsync')['default_args']

    def _get_client(self, info):
        try:
            client = Host(info['host'], info['username'],
                    info['password'], info.get('port', 22))
        except Exception, e:
            raise RsyncError('failed to connect to host %s: %s' % (info['host'], str(e)))
        if client.run_ssh('rsync --version', use_sudo=True)[-1] != 0:
            raise RsyncNotFound('failed to find rsync at host %s' % info['host'])
        return client

    def _get_sync_info(self, src, dst):
        self.src = parse_uri(src)
        self.dst = parse_uri(dst)
        if not self.src['host'] or not self.dst['host']:
            raise RsyncError('source and destination must include the host and user')
        self.src_host = self._get_client(self.src)
        self.dst_host = self._get_client(self.dst)

    def _sync(self, src, dst, exclude=None, delete=True):
        self._get_sync_info(src, dst)
        self.dst_host.makedirs(self.dst['path'])

        if self.src_host.host == self.dst_host.host:
            dst = self.dst['path']
            ssh_password = None
        else:
            dst = '%s@%s:%s' % (self.dst_host.username, self.dst_host.host, self.dst['path'])
            ssh_password = self.dst_host.password

        cmd = ['rsync']
        if self.default_args:
            cmd += self.default_args.split(' ')
        if exclude:
            cmd += ['--exclude=%s' % e for e in exclude]
        if delete:
            cmd.append('--delete-excluded' if exclude else '--delete')
        cmd += [self.src['path'], dst]
        cmd = ' '.join(cmd)
        try:
            stdout, return_code = self.src_host.run_ssh(cmd,
                    password=ssh_password,
                    use_sudo=True,
                    timeout=settings.PROCESS_TIMEOUT)
        finally:
            self.src_host.stop_cmd(cmd)
        if return_code not in (0, 23, 24):
            raise RsyncError(' '.join(stdout))
        return True

    def process(self, src, dst, exclude=None, delete=False):
        if not isinstance(src, (list, tuple)):
            src = [src]
        for src_ in src:
            self._sync(src_, dst, exclude=exclude, delete=delete)
        return True
