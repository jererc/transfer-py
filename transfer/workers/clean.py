from datetime import datetime, timedelta
import logging

from systools.system import loop, timeout, timer

from transfer import Transfer
from transfer.torrent import get_torrent_client, TransmissionError


DELTA_OBSOLETE = timedelta(days=180)

logger = logging.getLogger(__name__)


@loop(hours=6)
@timeout(minutes=30)
@timer()
def run():
    Transfer.remove({'finished': {
            '$lt': datetime.utcnow() - DELTA_OBSOLETE,
            }}, safe=True)
    try:
        get_torrent_client().clean_download_directory()
    except TransmissionError, e:
        logger.error('failed to get torrent client: %s' % str(e))
