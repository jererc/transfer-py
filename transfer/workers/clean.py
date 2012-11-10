from datetime import datetime, timedelta
import logging

from systools.system import loop, timeout, timer

from transfer import Transfer
from transfer.torrent import get_client


DELTA_OBSOLETE = timedelta(days=180)

logger = logging.getLogger(__name__)


@loop(hours=6)
@timeout(minutes=30)
@timer()
def run():
    Transfer.remove({'finished': {
            '$lt': datetime.utcnow() - DELTA_OBSOLETE,
            }}, safe=True)

    client = get_client()
    if client:
        client.clean_download_directory()
