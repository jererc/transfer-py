import sys
import os.path
import re
from urlparse import urlparse
from urllib import unquote_plus
from urllib2 import urlopen, URLError
import time
import logging

import pycurl

from filetools.title import clean
from filetools.media import move_file

from transfer import settings
from transfer.utils.utils import mkdtemp


RE_CONTENT_FILENAME = re.compile(r'filename="(.*?)"', re.I)

logger = logging.getLogger(__name__)


class HttpTransfer(object):

    def __init__(self):
        self.name = None
        self.total = 0
        self.transferred_current = 0
        self.transferred = 0
        self.last_callback = 0
        self.aborted = False

    def _callback(self, download_total, downloaded, upload_total, uploaded):
        now = time.time()
        if now - self.last_callback < settings.PROGRESS_CALLBACK_DELTA:
            return
        self.last_callback = now
        self.transferred_current = downloaded or uploaded

    def _get_remote_info(self, urls):
        info = []
        for url in urls:
            res = get_url_info(url)
            if not res:
                return
            if not res['filename']:
                logger.error('failed to get filename from %s' % url)
                return
            if not res['size']:
                logger.error('failed to get size from %s' % url)
            info.append(res)
        return info

    def _download_file(self, src, dst, timeout=settings.PROCESS_TIMEOUT):
        with open(dst, 'wb') as fd:
            def write(buf):
                if self.aborted:
                    return -1
                try:
                    fd.write(buf)
                except Exception:
                    return -1

            curl = pycurl.Curl()
            curl.setopt(pycurl.URL, str(src))
            curl.setopt(pycurl.FOLLOWLOCATION, 1)
            curl.setopt(pycurl.MAXREDIRS, 5)
            curl.setopt(pycurl.CONNECTTIMEOUT, 30)
            curl.setopt(pycurl.AUTOREFERER, 1)
            curl.setopt(pycurl.TIMEOUT, timeout)
            curl.setopt(pycurl.NOPROGRESS, 0)
            curl.setopt(pycurl.PROGRESSFUNCTION, self._callback)
            curl.setopt(pycurl.WRITEFUNCTION, write)
            try:
                curl.perform()
            except pycurl.error:
                logger.debug('aborted transfer from %s' % src)
                sys.exit(1)     # to avoid zombies
            finally:
                curl.close()

        return True

    def process(self, src, dst, temp_dir):
        if not isinstance(src, (tuple, list)):
            src = [src]
        info = self._get_remote_info(src)
        if not info:
            return

        self.total = sum([d['size'] for d in info])
        temp_files = []
        dst_files = []
        with mkdtemp(temp_dir) as temp_dst:
            for data in info:
                self.name = data['filename']
                temp_file = os.path.join(temp_dst, data['filename'])
                if not self._download_file(data['url'], temp_file):
                    return

                temp_files.append(temp_file)
                self.transferred = self.transferred_current

            for temp_file in temp_files:
                dst_file = move_file(temp_file, dst)
                if not dst_file:
                    return
                dst_files.append(dst_file)
                logger.info('moved finished transfer "%s" to %s' % (data['filename'], dst))

        return dst_files


def _get_filename(remote):
    if remote:
        data = remote.info().get('Content-Disposition')
        if data:
            res = RE_CONTENT_FILENAME.findall(data)
            if res:
                return clean(res[0])

def _get_size(remote):
    if remote:
        data = remote.info().get('Content-Length')
        if data:
            try:
                return int(data)
            except ValueError:
                pass
    return 0

def get_url_info(url):
    try:
        remote = urlopen(url)
    except URLError, e:
        logger.error('failed to open %s: %s' % (url, str(e)))
        return
    if remote:
        url = remote.geturl()
    filename = _get_filename(remote)
    if not filename:
        path = urlparse(url).path
        path = unquote_plus(path)
        filename = os.path.basename(path)

    return {
        'url': url,
        'filename': filename,
        'size': _get_size(remote),
        }

def download(src, dst, temp_dir):
    return HttpTransfer().process(src, dst, temp_dir)
