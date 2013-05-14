from sabnzbdrpc import Sabnzbd, SabnzbdError

from transfer import Settings


def get_nzb_client():
    info = Settings.get_settings('sabnzbd')
    return Sabnzbd(**info)
