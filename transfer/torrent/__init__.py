from transfer import Settings
from transfer.torrent.transmission import (Transmission, TransmissionError,
        TorrentError, TorrentExists)


def get_torrent_client():
    settings = Settings.get_settings('transmission')
    return Transmission(host=settings['host'], port=settings['port'],
            username=settings['username'], password=settings['password'])
