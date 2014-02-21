import logging

from flask import request, jsonify

from bson.objectid import ObjectId

from systools.system.webapp import crossdomain, serialize

from transfer import Transfer, Settings
from transfer.apps import app


logger = logging.getLogger(__name__)


@app.route('/status', methods=['GET'])
@crossdomain(origin='*')
def check_status():
    return jsonify(result='transfer')

@app.route('/transfer/create', methods=['POST', 'OPTIONS'])
@crossdomain(origin='*')
def create_transfer():
    data = request.json
    src = data.get('src')
    if not src:
        return jsonify(error='missing src')

    try:
        Transfer.add(src, data.get('dst'), data.get('type'))
    except Exception, e:
        return jsonify(error=str(e))
    return jsonify(result=True)

def _get_transfer(transfer):
    info = transfer.get('info') or {}
    return {
        'id': transfer['_id'],
        'name': info.get('name', 'N/A'),
        'type': transfer['type'],
        'src': transfer['src'],
        'dst': transfer['dst'],
        'size': transfer.get('total'),
        'transferred': transfer.get('transferred'),
        'transfer_rate': info.get('transfer_rate'),
        'progress': transfer.get('progress'),
        'tries': transfer['tries'],
        }

@app.route('/transfer/list', methods=['GET'])
@crossdomain(origin='*')
def list_transfers():
    items = [_get_transfer(t) for t in Transfer.find({'finished': None})]
    return serialize({'result': items})

@app.route('/transfer/remove', methods=['POST', 'OPTIONS'])
@crossdomain(origin='*')
def remove_transfer():
    data = request.json
    if not data.get('id'):
        return jsonify(error='missing id')
    Transfer.cancel(ObjectId(data['id']))
    return jsonify(result=True)

@app.route('/settings/list', methods=['GET', 'OPTIONS'])
@crossdomain(origin='*')
def list_settings():
    settings = {}
    for section in ('general', 'paths', 'transmission',
            'torrent', 'sabnzbd', 'rsync'):
        settings[section] = Settings.get_settings(section)
    return serialize({'result': settings})

@app.route('/settings/update', methods=['POST', 'OPTIONS'])
@crossdomain(origin='*')
def update_settings():
    data = request.json
    for section, settings in data.items():
        Settings.set_settings(section, settings, overwrite=True)
    return jsonify(result=True)
