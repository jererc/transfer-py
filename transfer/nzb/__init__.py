from sabnzbdrpc import Sabnzbd, ApiError

from transfer import Settings


def get_nzb_client():
    info = Settings.get_settings('sabnzbd')
    return Sabnzbd(**info)
