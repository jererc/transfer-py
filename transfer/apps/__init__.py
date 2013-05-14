from flask import Flask

app = Flask(__name__)

from transfer.apps import api
