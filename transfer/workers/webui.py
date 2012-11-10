from systools.system import webapp

from transfer import settings
from transfer.webui import app


def run():
    webapp.run(app, host='0.0.0.0', port=settings.WEBUI_PORT)
