import sys
from datetime import datetime
import time
import logging

from transfer import settings, Transfer, get_callable

from transfer.http import HttpTransfer
from transfer.rsync import RsyncTransfer, RsyncNotFound
from transfer.sftp import SftpTransfer
from transfer.ftp import FtpTransfer

from transfer.torrent import get_client
from transfer.torrent.exceptions import TorrentExists, TorrentError


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
        if now - self.last_callback < settings.PROGRESS_CALLBACK_INTERVAL:
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

        res = self.process(src, dst, settings.DEFAULT_TEMP_DIR)
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
        if now - self.last_callback < settings.PROGRESS_CALLBACK_INTERVAL:
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


class Torrent(object):

    def process_transfer(self, id):
        transfer = Transfer.find_one({'_id': id})
        if not transfer:
            return
        client = get_client()
        if not client:
            return

        try:
            transfer['info'] = client.add_torrent(transfer['src'])
        except TorrentExists, e:
            transfer['finished'] = datetime.utcnow()
            logger.debug('failed to start torrent: %s' % str(e))
        except TorrentError, e:
            transfer['started'] = None
            logger.error('failed to start torrent: %s' % str(e))
        Transfer.save(transfer, safe=True)
