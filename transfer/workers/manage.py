import os.path
from datetime import datetime, timedelta
import logging

from pymongo import DESCENDING

from systools.system import loop, timeout, timer

from filetools import media

from transfer import settings, Transfer, Settings, get_factory
from transfer.torrent import get_torrent_client, TransmissionError, TorrentError
from transfer.nzb import get_nzb_client, ApiError


TIMEOUT_MANAGE = 3600   # seconds

logger = logging.getLogger(__name__)


#
# NZB
#
@timer(30)
def manage_nzb(nzb_id, dst):
    try:
        client = get_nzb_client()
        nzb = client.get_nzb(nzb_id, history=True)
        if not nzb or not nzb['storage']:
            return
        if not os.path.exists(nzb['storage']):
            client.remove_nzb(nzb['nzo_id'], history=True, delete_files=True)
            logger.error('failed to find finished nzb directory "%s" (%s)' % (nzb['storage'], repr(nzb)))
        elif media.move_file(nzb['storage'], dst):
            client.remove_nzb(nzb['nzo_id'], history=True)
            logger.info('moved finished nzb %s to %s' % (nzb['storage'], dst))
    except ApiError, e:
        logger.error('nzb client error: %s' % str(e))

def get_nzb_transfer(id):
    return Transfer.find_one({'info.nzo_id': id},
            sort=[('created', DESCENDING)])

def get_float(val):
    try:
        return float(val)
    except ValueError:
        return 0

def manage_nzbs():
    client = get_nzb_client()

    for transfer in Transfer.find({
            'started': {'$ne': None},
            'finished': None,
            'type': 'binsearch',
            }):
        nzb_id = transfer['info'].get('nzo_id')
        if not nzb_id:
            continue
        info = client.get_nzb(nzb_id)
        if not info:
            Transfer.update({'_id': transfer['_id']},
                    {'$set': {'finished': datetime.utcnow()}},
                    safe=True)
        else:
            info['name'] = info.get('filename', transfer['info'].get('name'))
            total = get_float(info.get('mb', 0)) * 1024 ** 2
            Transfer.update({'_id': transfer['_id']},
                    {'$set': {
                        'total': total,
                        'transferred': total - get_float(info.get('mbleft', 0)) * 1024 ** 2,
                        'progress': get_float(info.get('percentage', 0)),
                        'info': info,
                    }}, safe=True)

    paths = Settings.get_settings('paths')

    # Manage queued nzbs
    for nzb in client.list_nzbs():
        transfer = get_nzb_transfer(nzb['nzo_id'])
        if not transfer:
            now = datetime.utcnow()
            Transfer.add(nzb['filename'], paths['default'],
                    type='binsearch', added=now, started=now, queued=now,
                    info={'nzo_id': nzb['nzo_id']})
        elif transfer['finished']:
            client.remove_nzb(nzb['nzo_id'])
            logger.info('removed finished nzb "%s" (%s)' % (nzb['filename'], nzb['nzo_id']))

    # Manage finished nzbs
    for nzb in client.list_nzbs(history=True):
        transfer = get_nzb_transfer(nzb['nzo_id'])
        if nzb['status'] == 'Completed':
            dst = transfer['dst'] if transfer else paths['default']
        elif nzb['status'] == 'Failed':
            dst = paths['invalid']
        else:
            continue
        target = '%s.workers.manage.manage_nzb' % settings.PACKAGE_NAME
        get_factory().add(target=target,
                kwargs={'nzb_id': nzb['nzo_id'], 'dst': dst},
                timeout=TIMEOUT_MANAGE)


#
# Torrent
#
@timer(30)
def manage_torrent(hash, dst):
    try:
        client = get_torrent_client()
        torrent = client.get_torrent(hash=hash)
        if not torrent:
            return

        if not client.check_torrent_files(torrent,
                check_unfinished=settings.CHECK_UNFINISHED_TORRENTS):
            invalid_dir = Settings.get_settings('paths')['invalid']
            if torrent.progress == 100 and not client.move_files(torrent, invalid_dir):
                return
            if client.remove_torrent(hash=hash, delete_data=True):
                logger.info('removed invalid torrent "%s" (%s%% done)' % (torrent.name, int(torrent.progress)))
            Transfer.update({'info.hash': hash, 'finished': None},
                    {'$set': {'finished': datetime.utcnow()}}, safe=True)
            return

        if torrent.progress == 100:
            destination = client.get_destination_dir(torrent, dst)
            if not client.move_files(torrent, destination):
                return
            if client.remove_torrent(hash=hash):
                logger.info('moved finished torrent "%s" to %s' % (torrent.name, dst))
            Transfer.update({'info.hash': hash, 'finished': None},
                    {'$set': {'finished': datetime.utcnow()}}, safe=True)
            return

        torrent_settings = Settings.get_settings('torrent')
        now = datetime.utcnow()

        inactive_delta = torrent_settings['inactive_delta']
        if inactive_delta:
            date = torrent.date_active or torrent.date_added
            if date < now - timedelta(hours=inactive_delta) \
                    and client.remove_torrent(hash=hash, delete_data=True):
                logger.debug('removed inactive torrent "%s": no activity since %s' % (torrent.name, date))
                return

        added_delta = torrent_settings['added_delta']
        if added_delta:
            date = torrent.date_added
            if date < now - timedelta(hours=added_delta) \
                    and client.remove_torrent(hash=hash, delete_data=True):
                logger.debug('removed obsolete torrent "%s": added %s' % (torrent.name, date))

    except TransmissionError, e:
        logger.error('torrent client error: %s' % str(e))

def manage_torrents():
    client = get_torrent_client()

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

    default_dir = Settings.get_settings('paths')['default']
    for torrent in client.iter_torrents():
        transfer = Transfer.find_one({'info.hash': torrent.hash},
                sort=[('created', DESCENDING)])
        if not transfer or (transfer['finished'] \
                and torrent.date_added > transfer['finished']):
            now = datetime.utcnow()
            Transfer.add(torrent.magnet_url, default_dir,
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

@loop(10)
@timeout(minutes=30)
@timer()
def run():
    try:
        manage_nzbs()
    except ApiError, e:
        logger.error('nzb client error: %s' % str(e))

    try:
        manage_torrents()
    except TransmissionError, e:
        logger.error('torrent client error: %s' % str(e))
