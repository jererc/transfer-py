#!/usr/bin/env python
import sys
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

from systools.system import check_commands, get_package_modules

from tracy import DbHandler

from transfer import settings, get_factory, Transfer


CMDS = ['rsync', 'unzip', 'unrar']
WORKERS_DIR = 'workers'

logging.basicConfig(level=logging.DEBUG)


def clean_aborted():
    Transfer.update({'is_mount': True, 'finished': None},
            {'$set': {'finished': datetime.utcnow()}}, multi=True, safe=True)
    Transfer.update({'finished': None, 'queued': None},
            {'$set': {'started': None}}, multi=True, safe=True)

def main():
    if not check_commands(CMDS):
        sys.exit(1)

    clean_aborted()

    factory = get_factory()
    factory.remove(daemon=True)

    # Logging handlers
    fh = RotatingFileHandler(settings.LOG_FILE, 'a',
            settings.LOG_SIZE, settings.LOG_COUNT)
    fh.setFormatter(logging.Formatter(settings.LOG_FORMAT))
    dh = DbHandler(logging.ERROR)
    factory.logging_handlers = (fh, dh)

    for module in get_package_modules(WORKERS_DIR):
        if module != '__init__':
            target = '%s.%s.%s.run' % (settings.PACKAGE_NAME, WORKERS_DIR, module)
            factory.add(target=target, daemon=True)

    factory.run()


if __name__ == '__main__':
    main()
