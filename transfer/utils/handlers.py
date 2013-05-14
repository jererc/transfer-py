import sys
import os.path
from datetime import datetime
import time
from urlparse import urlparse, parse_qs
import logging

from mediacore.web.search.plugins.binsearch import get_nzb, BinsearchException
from mediacore.web.search.plugins.filestube import get_download_urls, FilestubeException

from filetools.title import clean

from transfer import settings, Transfer, Settings, get_callable

from transfer.http import HttpTransfer
from transfer.rsync import RsyncTransfer, RsyncNotFound
from transfer.sftp import SftpTransfer
from transfer.ftp import FtpTransfer
from transfer.nzb import get_nzb_client, ApiError
from transfer.torrent import (get_torrent_client, TransmissionError,
        TorrentError, TorrentExists)

from transfer.utils.utils import mkdtemp


logger = logging.getLogger(__name__)


class Http(HttpTransfer):

    def _callback(self, download_total, downloaded, upload_total, uploaded):
        if not Transfer.find_one({
                '_id': self.transfer['_id'],
                'finished': None,
                }):
            self.aborted = True
            return

        now = time.time()
        if now - self.last_callback < settings.PROGRESS_CALLBACK_DELTA:
            return
        self.last_callback = now

        transferred = downloaded or uploaded
        self.transferred_current = transferred
        transferred += self.transferred
        self.transfer['total'] = self.total
        self.transfer['transferred'] = transferred
        total = float(self.transfer['total'])
        self.transfer['progress'] = transferred * 100 / total if total else 0
        self.transfer['info']['name'] = self.name
        Transfer.save(self.transfer, safe=True)

    def process_transfer(self, id):
        self.transfer = Transfer.find_one({'_id': id})
        if not self.transfer:
            return

        src = self.transfer['src']
        dst = self.transfer['dst']
        if not isinstance(src, (tuple, list)):
            src = [src]

        temp_dir = Settings.get_settings('paths')['tmp']
        res = self.process(src, dst, temp_dir)
        if res:
            self.transfer['info']['files'] = res
            self.transfer['transferred'] = self.total
            self.transfer['progress'] = 100
            logger.info('finished http transfer %s to %s' % (src, dst))
        else:
            self.transfer['started'] = None
            logger.error('failed to process http transfer %s to %s' % (src, dst))
        self.transfer['finished'] = datetime.utcnow()
        Transfer.save(self.transfer, safe=True)


class Filestube(Http):

    def process_transfer(self, id):
        self.transfer = Transfer.find_one({'_id': id})
        if not self.transfer:
            return

        try:
            src = get_download_urls(self.transfer['src'])
        except FilestubeException, e:
            logger.error('failed to get filestube urls for %s: %s' % (self.transfer['src'], str(e)))
            return

        dst = self.transfer['dst']

        temp_dir = Settings.get_settings('paths')['tmp']
        res = self.process(src, dst, temp_dir)
        if res:
            self.transfer['info']['files'] = res
            self.transfer['transferred'] = self.total
            self.transfer['progress'] = 100
            logger.info('finished http transfer %s to %s' % (src, dst))
        else:
            self.transfer['started'] = None
            logger.error('failed to process http transfer %s to %s' % (src, dst))
        self.transfer['finished'] = datetime.utcnow()
        Transfer.save(self.transfer, safe=True)


class Rsync(RsyncTransfer):

    def process_transfer(self, id):
        self.transfer = Transfer.find_one({'_id': id})
        if not self.transfer:
            return

        src = self.transfer['src']
        dst = self.transfer['dst']
        parameters = self.transfer.get('parameters', {})
        try:
            self.process(src, dst, exclude=parameters.get('exclusions'),
                    delete=parameters.get('delete', True))
            self.transfer['progress'] = 100
            logger.info('finished rsync transfer %s to %s' % (src, dst))
        except RsyncNotFound:   # sftp fallback
            return get_callable('sftp')(id)
        except Exception, e:
            self.transfer['started'] = None
            logger.error('failed to process rsync transfer %s to %s: %s' % (src, dst, str(e)))
        self.transfer['finished'] = datetime.utcnow()
        Transfer.save(self.transfer, safe=True)


class Sftp(SftpTransfer):

    def _callback(self, processed, total):
        if not Transfer.find_one({
                '_id': self.transfer['_id'],
                'finished': None,
                }):
            logger.info('aborted sftp transfer %s to %s' % (self.transfer['src'], self.transfer['dst']))
            sys.exit(1)     # to avoid zombies

        now = time.time()
        if now - self.last_callback < settings.PROGRESS_CALLBACK_DELTA:
            return
        self.last_callback = now
        self.transfer['transferred'] = self.transferred
        self.transfer['info']['name'] = self.name
        Transfer.save(self.transfer, safe=True)

    def process_transfer(self, id):
        self.transfer = Transfer.find_one({'_id': id})
        if not self.transfer:
            return

        src = self.transfer['src']
        dst = self.transfer['dst']
        parameters = self.transfer.get('parameters', {})
        exclude = parameters.get('exclusions')
        if exclude:
            exclude = [r'^%s' % e for e in exclude]
        try:
            self.process(src, dst, exclude=exclude,
                    delete=parameters.get('delete', True))
            self.transfer['transferred'] = self.transferred
            self.transfer['progress'] = 100
            logger.info('finished sftp transfer %s to %s' % (src, dst))
        except Exception, e:
            self.transfer['started'] = None
            logger.error('failed to process sftp transfer %s to %s: %s' % (src, dst, str(e)))
        self.transfer['finished'] = datetime.utcnow()
        Transfer.save(self.transfer, safe=True)


class Ftp(FtpTransfer):

    def process_transfer(self, id):
        self.transfer = Transfer.find_one({'_id': id})
        if not self.transfer:
            return

        src = self.transfer['src']
        dst = self.transfer['dst']
        parameters = self.transfer.get('parameters', {})
        exclude = parameters.get('exclusions')
        if exclude:
            exclude = [r'^%s' % e for e in exclude]
        try:
            self.process(src, dst, exclude=exclude,
                    delete=parameters.get('delete', True))
            self.transfer['transferred'] = self.transferred
            self.transfer['progress'] = 100
            logger.info('finished ftp transfer %s to %s' % (src, dst))
        except Exception, e:
            self.transfer['started'] = None
            logger.error('failed to process ftp transfer %s to %s: %s' % (src, dst, str(e)))
        self.transfer['finished'] = datetime.utcnow()
        Transfer.save(self.transfer, safe=True)


class Binsearch(object):

    def process_transfer(self, id):
        transfer = Transfer.find_one({'_id': id, 'queued': None})
        if not transfer:
            return

        qs = parse_qs(urlparse(transfer['src']).query)
        try:
            name = clean(qs['b'][0])
        except KeyError:
            Transfer.update({'_id': transfer['_id']},
                    {'$set': {'finished': datetime.utcnow()}}, safe=True)
            logger.error('failed to get nzb name from %s' % transfer['src'])
            return

        try:
            nzb_data = get_nzb(transfer['src'])
        except BinsearchException, e:
            Transfer.update({'_id': transfer['_id']},
                    {'$set': {'started': None}}, safe=True)
            logger.error('failed to get nzb data from %s: %s' % (transfer['src'], str(e)))
            return

        temp_dir = Settings.get_settings('paths')['tmp']
        with mkdtemp(temp_dir) as temp_dst:
            temp_file = os.path.join(temp_dst, '%s.nzb' % name)
            with open(temp_file, 'wb') as fd:
                fd.write(nzb_data)
            try:
                nzb_id = get_nzb_client().add_nzb(temp_file)
                Transfer.update({'_id': transfer['_id']},
                        {'$set': {
                            'queued': datetime.utcnow(),
                            'info.nzo_id': nzb_id,
                            'info.name': name,
                        }}, safe=True)
            except ApiError, e:
                Transfer.update({'_id': transfer['_id']}, {'$set': {
                        'started': None,
                        'tries': 0,
                        }}, safe=True)
                logger.error('failed to start nzb: %s' % str(e))


class Torrent(object):

    def process_transfer(self, id):
        transfer = Transfer.find_one({'_id': id, 'queued': None})
        if not transfer:
            return

        try:
            info = get_torrent_client().add_torrent(transfer['src'])
            Transfer.update({'_id': transfer['_id']},
                    {'$set': {
                        'queued': datetime.utcnow(),
                        'info': info,
                    }}, safe=True)
        except TorrentExists, e:
            Transfer.update({'_id': transfer['_id']},
                    {'$set': {'finished': datetime.utcnow()}},
                    safe=True)
            logger.debug('failed to start torrent: %s' % str(e))
        except (TransmissionError, TorrentError), e:
            Transfer.update({'_id': transfer['_id']}, {'$set': {
                    'started': None,
                    'tries': 0,
                    }}, safe=True)
            logger.error('failed to start torrent: %s' % str(e))
