from systools.system import webapp

from transfer.apps import app

from transfer import settings


def run():
    webapp.run(app, host='0.0.0.0', port=settings.API_PORT)
