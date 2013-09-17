from sabnzbdrpc import Sabnzbd, SabnzbdError

from transfer import Settings


def get_nzb_client():
    settings = Settings.get_settings('sabnzbd')
    return Sabnzbd(host=settings['host'], port=settings['port'],
            api_key=settings['api_key'])
