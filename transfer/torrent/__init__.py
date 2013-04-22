from transfer import Settings
from transfer.torrent.transmission import Transmission


def get_client():
    info = Settings.get_settings('transmission')
    client = Transmission(**info)
    if client.logged:
        return client
