from datetime import datetime
import logging

from factory import Factory

from transfer import settings
from transfer.utils.db import connect, Model
from transfer.utils.utils import get_transfer_type


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
connect(settings.DB_NAME)


class InvalidTransfer(Exception): pass


class Transfer(Model):
    COL = 'transfers'

    @classmethod
    def add(cls, src, dst, type=None, **parameters):
        if not type:
            type = get_transfer_type(src, dst)
        if not type or not get_callable(type):
            raise InvalidTransfer('unhandled transfer type for %s to %s' % (src, dst))

        doc = {
            'src': src,
            'dst': dst,
            'type': type,
            'total': None,
            'transferred': 0,
            'progress': 0,
            'created': datetime.utcnow(),
            'added': None,
            'started': None,
            'finished': None,
            'tries': 0,
            'info': {},
            }
        doc.update(parameters)
        doc['info']['name'] = ', '.join(src) if isinstance(src, (list, tuple)) else src
        return cls.insert(doc, safe=True)

    @classmethod
    def cancel(cls, id):
        cls.update({'_id': id},
                {'$set': {'finished': datetime.utcnow()}}, safe=True)


def get_factory():
    return Factory(collection=settings.PACKAGE_NAME)

def get_callable(type):
    try:
        module = __import__('transfer.utils.handlers', globals(), locals(), ['handlers'], -1)
    except ImportError, e:
        logger.error(str(e))
        return
    cls = getattr(module, type.capitalize(), None)
    if cls:
        return getattr(cls(), 'process_transfer')
