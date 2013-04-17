PACKAGE_NAME = 'transfer'

MAX_TRIES = 3
RETRY_DELAY = 60    # seconds
PROCESS_TIMEOUT = 3600 * 6  # seconds
PROGRESS_CALLBACK_INTERVAL = 5  # seconds
DEFAULT_TEMP_DIR = '/tmp'
WORKERS_LIMITS = {
    'http': 2,
    'rsync': 4,
    'sftp': 2,
    }

# Torrent
TRANSMISSION_INFO = {
    'host': 'localhost',
    'port': 9091,
    'username': None,
    'password': None,
    }
DEFAULT_TORRENT_DST = '/home/user/Downloads'
DST_INVALID = '/home/user/Downloads/invalid'
DELTA_TORRENT_ACTIVE = 24 * 4   # hours
DELTA_TORRENT_ADDED = 24 * 15   # hours
CHECK_UNFINISHED_TORRENTS = False

# Rsync
DEFAULT_RSYNC_ARGS = ['-ax', '--ignore-errors']

# Db
DB_NAME = 'transfer'

WEBUI_PORT = 8002

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
