from transfer import settings
from transfer.torrent.transmission import Transmission


def get_client():
    client = Transmission(**settings.TRANSMISSION_INFO)
    if client.logged:
        return client
