import os
import re
from datetime import datetime
import logging

import transmissionrpc

from systools.system import dotdict

from filetools import media
from filetools.title import clean
from filetools.download import check_download_file

from transfer.torrent.exceptions import TorrentExists, TorrentError


RE_HASH = re.compile(r'\bbtih:(.*?)\W', re.I)

logger = logging.getLogger(__name__)


class Transmission(object):

    def __init__(self, host='localhost', port=9091, username=None, password=None):
        try:
            self.client = transmissionrpc.Client(host, port=port, user=username, password=password)
            self.logged = True
            self.download_dir = self.client.get_session().download_dir
        except Exception, e:
            self.logged = False
            logger.error('failed to connect to transmission rpc server %s:%s: %s' % (host, port, str(e)))

    def add(self, url, delete_torrent=True):
        '''Add a torrent.

        :return: torrent object
        '''
        try:
            res = self.client.add_uri(url)
        except Exception, e:
            hash = get_hash(url)
            if hash and self.get(hash):
                raise TorrentExists('url %s is already queued (%s)' % (url, hash))
            raise TorrentError('failed to add url %s: %s' % (repr(url), str(e)))

        if os.path.isfile(url) and delete_torrent:
            media.remove_file(url)

        try:
            id = res.items()[0][0]
        except Exception, e:
            logger.error('failed to get torrent id from %s: %s' % (res, str(e)))
            return
        torrent = self.get(id)
        if not torrent:
            logger.error('failed to get torrent from transmission id %s' % id)
            return
        return torrent

    def torrents(self):
        '''Iterate torrents.
        '''
        for id in self.client.list():
            res = self.get(id)
            if res:
                yield res

    def get(self, id):
        '''Get a torrent.

        :param id: transmission id or torrent hash
        '''
        try:
            info = self.client.info(id)
        except Exception, e:
            raise TorrentError('failed to get torrent %s: %s' % (id, str(e)))
        if not info:
            return

        res = info.items()[0][1]
        return dotdict({
            'hash': res.hashString.lower(),
            'id': res.id,
            'name': res.name,
            'error_string': res.errorString,
            'status': res.status,
            'torrent_file': res.torrentFile,
            'download_dir': res.downloadDir,
            'files': [f['name'] for f in res.files().values()],
            'size': res.totalSize,
            'transferred': res.downloadedEver,
            'progress': res.progress,
            'transfer_rate': res.rateDownload,
            'date_added': datetime.utcfromtimestamp(res.addedDate),
            'date_active': datetime.utcfromtimestamp(res.activityDate) if res.activityDate else None,
            })

    def remove(self, id, delete_data=False):
        '''Remove a torrent.

        :param id: transmission id or torrent hash

        :return: True if successful
        '''
        res = self.get(id)
        if not res:
            return
        if delete_data and not res.files:    # remove requests fail for magnet links without metadata yet
            delete_data = False

        try:
            self.client.remove(id, delete_data=delete_data)
        except Exception:
            logger.exception('exception')
            return
        return True

    def check_torrent_files(self, torrent):
        finished = torrent.progress == 100
        for file in torrent.files:
            file = os.path.join(torrent.download_dir, file)
            if not check_download_file(file + '.part', finished_file=file, finished=finished):
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
        for torrent in self.torrents():
            for file in torrent.files:
                files_queued.append(os.path.join(torrent.download_dir, file))

        # Remove files not queued
        for file in media.iter_files(self.download_dir):
            file_source, ext = os.path.splitext(file)
            if ext == '.part' and file_source in files_queued:
                continue
            elif os.path.isfile(file) and file not in files_queued:
                if media.remove_file(file):
                    logger.info('removed file %s: not queued' % file.encode('utf-8'))

        # Remove empty directories not queued
        for path in media.iter_files(self.download_dir, incl_files=False, incl_dirs=True):
            if not os.listdir(path) and not self._is_dir_queued(path, files_queued):
                if media.remove_file(path):
                    logger.info('removed empty directory %s: not queued' % path.encode('utf-8'))


def get_hash(url):
    res = RE_HASH.findall(url)
    if res:
        return res[0]
