from transfer import Settings
from transfer.torrent.transmission import (Transmission, TransmissionError,
        TorrentError, TorrentExists)


def get_torrent_client():
    info = Settings.get_settings('transmission')
    return Transmission(**info)
