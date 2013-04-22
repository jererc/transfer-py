PACKAGE_NAME = 'transfer'
DB_NAME = 'transfer'
API_PORT = 9002

WORKERS_LIMITS = {
    'http': 2,
    'rsync': 4,
    'sftp': 2,
    }
PROCESS_TIMEOUT = 3600 * 6  # seconds
PROGRESS_CALLBACK_DELTA = 5  # seconds
CHECK_UNFINISHED_TORRENTS = False


# MAX_TRIES = 3
# RETRY_DELAY = 60    # seconds
# DEFAULT_TEMP_DIR = '/tmp'
# DEFAULT_TORRENT_DST = '/home/user/Downloads'
# DST_INVALID = '/home/user/Downloads/invalid'
# DELTA_TORRENT_ACTIVE = 24 * 4   # hours
# DELTA_TORRENT_ADDED = 24 * 15   # hours
# DEFAULT_RSYNC_ARGS = ['-ax', '--ignore-errors']


# Logging
LOG_FILE = '/home/user/log/transfer.log'
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
LOG_SIZE = 100000   # Bytes
LOG_COUNT = 100


# Import local settings
try:
    from local_settings import *
except ImportError:
    pass
