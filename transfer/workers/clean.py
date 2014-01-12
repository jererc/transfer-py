import os.path
from glob import glob
from datetime import datetime, timedelta
import logging

from systools.system import loop, timeout, timer

from filetools.media import remove_file

from transfer import Transfer, Settings
from transfer.torrent import get_torrent_client, TransmissionError
from transfer.nzb import get_nzb_client, SabnzbdError


DELTA_OBSOLETE = timedelta(days=30)

logger = logging.getLogger(__name__)


def clean_torrents():
    try:
        get_torrent_client().clean_download_directory()
    except TransmissionError, e:
        logger.error('failed to get torrent client: %s', str(e))

def clean_nzbs():
    try:
        client = get_nzb_client()
        nzbs = client.list_nzbs(history=False) + client.list_nzbs(history=True)
        if nzbs:
            return

        config = client.get_config()
        base_path = str(Settings.get_settings('sabnzbd')['base_path'])
        for name in ('download_dir', 'complete_dir'):
            path = config['misc'].get(name)
            if not path:
                logger.error('failed to get sabnzbd %s', name)
                continue
            path = str(os.path.join(base_path, path))
            if not os.path.exists(path):
                logger.error('sabnzbd %s path %s does not exist', name, path)
                continue

            for file in glob(path + '/*'):
                if remove_file(file):
                    logger.info('removed obsolete sabnzbd path %s', file)

    except SabnzbdError, e:
        logger.error('nzb client error: %s', str(e))

@loop(hours=6)
@timeout(minutes=30)
@timer()
def run():
    Transfer.remove({'finished': {
            '$lt': datetime.utcnow() - DELTA_OBSOLETE,
            }}, safe=True)

    if Settings.get_settings('transmission').get('active', True):
        clean_torrents()

    if Settings.get_settings('sabnzbd').get('active', True):
        clean_nzbs()
