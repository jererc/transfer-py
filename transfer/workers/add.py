from datetime import datetime, timedelta
import logging

from systools.system import loop, timer

from transfer import settings, Transfer, Settings, get_factory, get_callable


logger = logging.getLogger(__name__)


def add_running(running, type):
    running.setdefault(type, 0)
    running[type] += 1

def process(id, type):
    callable = get_callable(type)
    if callable:
        callable(id)

@loop(10)
@timer()
def run():
    running = {}
    for res in Transfer.find({
            'started': {'$ne': None},
            'finished': None,
            }):
        add_running(running, res['type'])

    settings_ = Settings.get_settings('general')
    retry_delta = timedelta(seconds=settings_['retry_delta'])

    for transfer in Transfer.find({
            'finished': None,
            '$or': [
                {'added': None},
                {
                'added': {'$lt': datetime.utcnow() - retry_delta},
                'started': None,
                'tries': {'$lt': settings_['max_tries']},
                },
                ],
            }):
        limit = settings.WORKERS_LIMITS.get(transfer['type'])
        if limit and running.get(transfer['type'], 0) >= limit:
            continue

        factory = get_factory()
        target = '%s.workers.add.process' % settings.PACKAGE_NAME
        if factory.get(target=target,
                args=(transfer['_id'], transfer['type'])):
            continue
        factory.add(target=target,
                args=(transfer['_id'], transfer['type']),
                timeout=settings.PROCESS_TIMEOUT)

        now = datetime.utcnow()
        Transfer.update({'_id': transfer['_id']}, {
                '$set': {'added': now, 'started': now},
                '$inc': {'tries': 1},
                }, safe=True)

        add_running(running, transfer['type'])

        count_str = ' (#%s)' % transfer['tries'] if transfer['tries'] > 1 else ''
        logger.info('started%s %s transfer %s to %s', count_str, transfer['type'], transfer['src'], transfer['dst'])
