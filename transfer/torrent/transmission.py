import os
import re
from datetime import datetime
import logging

import transmissionrpc

from systools.system import dotdict

from filetools import media
from filetools.title import clean
from filetools.download import check_download_file


RE_HASH = re.compile(r'\bbtih:(.*?)\W', re.I)
RE_DUPLICATE = re.compile('duplicate torrent', re.I)

logger = logging.getLogger(__name__)


class TransmissionError(Exception): pass
class TorrentError(Exception): pass
class TorrentExists(Exception): pass


class Transmission(object):

    def __init__(self, host='localhost', port=9091,
            username=None, password=None):
        try:
            self.client = transmissionrpc.Client(host,
                    port=port, user=username, password=password)
            self.download_dir = self.client.get_session().download_dir
        except Exception, e:
            raise TransmissionError('failed to connect to transmission rpc server %s:%s: %s' % (host, port, str(e)))

    def add_torrent(self, url, delete_torrent=True):
        try:
            self.client.add_torrent(url)
        except Exception, e:
            if RE_DUPLICATE.search(str(e)):
                raise TorrentExists('url %s is already queued' % url)
            raise TorrentError('failed to add url %s: %s' % (url, str(e)))

        if os.path.isfile(url) and delete_torrent:
            media.remove_file(url)

        torrent = self.get_torrent(hash=get_hash(url))
        if torrent:
            return torrent
        raise TorrentError('failed to add torrent %s' % url)

    def _get_torrent(self, torrent):
        return dotdict({
            'hash': torrent.hashString.lower(),
            'id': torrent.id,
            'name': torrent.name,
            'status': torrent.status,
            'error_string': torrent.errorString,
            'magnet_url': torrent.magnetLink,
            'torrent_file': torrent.torrentFile,
            'download_dir': torrent.downloadDir,
            'files': [f['name'] for f in torrent.files().values()],
            'size': torrent.totalSize,
            'transferred': torrent.downloadedEver,
            'progress': torrent.progress,
            'transfer_rate': torrent.rateDownload,
            'date_added': datetime.utcfromtimestamp(torrent.addedDate),
            'date_active': datetime.utcfromtimestamp(torrent.activityDate) if torrent.activityDate else None,
            })

    def iter_torrents(self):
        for res in self.client.get_torrents():
            yield self._get_torrent(res)

    def get_torrent(self, id=None, hash=None):
        if hash:    # transmissionrpc does not handle query by hash, even though the documentation states it
            for res in self.iter_torrents():
                if res.hash == hash:
                    return res
            return

        try:
            res = self.client.get_torrent(id)
        except KeyError:
            return
        except Exception, e:
            raise TorrentError('failed to get torrent id %s: %s' % (id, str(e)))
        return self._get_torrent(res)

    def remove_torrent(self, id=None, hash=None, delete_data=False):
        res = self.get_torrent(id=id, hash=hash)
        if not res:
            return
        if delete_data and not res.files:    # remove data requests fail for magnets without metadata
            delete_data = False

        try:
            self.client.remove_torrent(res.id, delete_data=delete_data)
        except Exception:
            logger.exception('exception')
            return
        return True

    def check_torrent_files(self, torrent, check_unfinished=True):
        finished = torrent.progress == 100
        if not check_unfinished and not finished:
            return True
        for file in torrent.files:
            file = os.path.join(torrent.download_dir, file)
            if not check_download_file(file + '.part',
                    finished_file=file, finished=finished):
                return
            elif not check_download_file(file, finished=finished):
                return
        return True

    def get_destination_dir(self, torrent, dst):
        '''Get the base directory where to move the torrent files.
        '''
        root_files = [f for f in torrent.files if '/' not in f]
        if not root_files:
            base_dirs = set([r.split('/')[0] for r in torrent.files])
            if len(base_dirs) == 1:
                return dst
        return os.path.join(dst, clean(torrent.name))

    def move_files(self, torrent, dst):
        '''Move files to the destination directory.

        :param torrent: torrent
        :param dst: destination root directory

        :return: True if successful
        '''
        res = True
        for file in torrent.files:
            src = os.path.join(torrent.download_dir, file)
            if os.path.isfile(src):
                dst_dir = os.path.dirname(os.path.join(dst, file))
                if not media.move_file(src, dst_dir):
                    res = False
        return res

    def _is_dir_queued(self, directory, files):
        for file in files:
            if file.startswith('%s/' % directory):
                return True

    def clean_download_directory(self):
        files_queued = []
        for torrent in self.iter_torrents():
            for file in torrent.files:
                files_queued.append(os.path.join(torrent.download_dir, file))

        # Remove files not queued
        for file in media.iter_files(self.download_dir):
            file_source, ext = os.path.splitext(file)
            if ext == '.part' and file_source in files_queued:
                continue
            elif os.path.isfile(file) and file not in files_queued:
                if media.remove_file(file):
                    logger.info('removed file %s: not queued', file.encode('utf-8'))

        # Remove empty directories not queued
        for path in media.iter_files(self.download_dir,
                incl_files=False, incl_dirs=True):
            if not os.listdir(path) \
                    and not self._is_dir_queued(path, files_queued):
                if media.remove_file(path):
                    logger.info('removed empty directory %s: not queued', path.encode('utf-8'))


def get_hash(url):
    res = RE_HASH.findall(url)
    if res:
        return res[0].lower()
