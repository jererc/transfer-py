from datetime import datetime, timedelta
import logging

from pymongo import DESCENDING

from systools.system import loop, timeout, timer

from transfer import settings, Transfer, get_factory
from transfer.torrent import get_client
from transfer.torrent.exceptions import TorrentError


TIMEOUT_MANAGE = 3600   # seconds

logger = logging.getLogger(__name__)


def update_transfer(hash):
    Transfer.update({'info.hash': hash, 'finished': None},
            {'$set': {'finished': datetime.utcnow()}}, safe=True)

@timer(30)
def manage_torrent(hash, dst):
    client = get_client()
    if not client:
        return
    torrent = client.get_torrent(hash=hash)
    if not torrent:
        return

    if not client.check_torrent_files(torrent,
            check_unfinished=settings.CHECK_UNFINISHED_TORRENTS):
        if torrent.progress == 100 and not client.move_files(torrent, settings.DST_INVALID):
            return
        if client.remove_torrent(hash=hash, delete_data=True):
            logger.info('removed invalid torrent "%s" (%s%% done)' % (torrent.name, int(torrent.progress)))
        update_transfer(hash)

    elif torrent.progress == 100:
        destination = client.get_destination_dir(torrent, dst)
        if not client.move_files(torrent, destination):
            return
        if client.remove_torrent(hash=hash):
            logger.info('moved finished torrent "%s" to %s' % (torrent.name, dst))
        update_transfer(hash)

    elif settings.DELTA_TORRENT_ACTIVE:
        date = torrent.date_active or torrent.date_added
        if date < datetime.utcnow() - timedelta(hours=settings.DELTA_TORRENT_ACTIVE):
            if client.remove_torrent(hash=hash, delete_data=True):
                logger.debug('removed inactive torrent "%s": no activity since %s' % (torrent.name, date))

    elif settings.DELTA_TORRENT_ADDED \
            and torrent.date_added < datetime.utcnow() - timedelta(hours=settings.DELTA_TORRENT_ADDED):
        if client.remove_torrent(hash=hash, delete_data=True):
            logger.debug('removed obsolete torrent "%s": added %s' % (torrent.name, torrent.date_added))

@loop(10)
@timeout(minutes=30)
@timer()
def run():
    client = get_client()
    if not client:
        return

    for transfer in Transfer.find({
            'started': {'$ne': None},
            'finished': None,
            'type': 'torrent',
            }):
        hash = transfer['info'].get('hash')
        if not hash:
            continue
        try:
            torrent = client.get_torrent(hash=hash)
        except TorrentError:
            continue
        if not torrent:
            transfer['finished'] = datetime.utcnow()
            logger.debug('torrent %s is not queued' % hash)
        else:
            transfer['info'] = torrent
            transfer['transferred'] = torrent.transferred
            transfer['total'] = torrent.size
            transfer['progress'] = torrent.progress
        Transfer.save(transfer, safe=True)

    for torrent in client.iter_torrents():
        transfer = Transfer.find_one({'info.hash': torrent.hash},
                sort=[('created', DESCENDING)])
        if not transfer or (transfer['finished'] \
                and torrent.date_added > transfer['finished']):
            now = datetime.utcnow()
            Transfer.add(torrent.magnet_url, settings.DEFAULT_TORRENT_DST,
                    type='torrent', added=now, started=now,
                    info={'hash': torrent.hash})
        elif transfer['finished']:
            client.remove_torrent(hash=torrent.hash, delete_data=True)
            logger.debug('removed finished torrent "%s" (%s)' % (torrent.name, torrent.hash))
        else:
            target = '%s.workers.manage.manage_torrent' % settings.PACKAGE_NAME
            get_factory().add(target=target,
                    kwargs={'hash': torrent.hash, 'dst': transfer['dst']},
                    timeout=TIMEOUT_MANAGE)
