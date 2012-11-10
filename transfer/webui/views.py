import logging

from flask import jsonify, request, render_template

from pymongo.objectid import ObjectId

from transfer import Transfer
from transfer.webui import app


logger = logging.getLogger(__name__)


@app.route('/')
def index():
    items = Transfer.find({'finished': None})
    return render_template('transfers.html', items=items)

@app.route('/transfers/add')
def add():
    src = request.args.get('src')
    dst = request.args.get('dst')
    if not src or not dst:
        return jsonify(message='missing source or destination')

    try:
        Transfer.add(src, dst, request.args.get('type'))
    except Exception, e:
        return jsonify(message=str(e))
    return jsonify(message=None)

@app.route('/transfers/update')
def update():
    transfer_id = ObjectId(request.args.get('id'))
    transfer = Transfer.find_one({'_id': transfer_id})
    if not transfer:
        return jsonify(name=None)
    params = {
        'name': truncate(transfer['info']['name']),
        'progress': int(transfer.get('progress') or 0),
        'transferred': int(transfer.get('transferred') or 0) / 1024 ** 2,
        'size': int(transfer.get('total') or 0) / 1024 ** 2,
        }
    return jsonify(**params)

@app.route('/transfers/cancel')
def cancel():
    transfer_id = ObjectId(request.args.get('id'))
    Transfer.cancel(transfer_id)
    return jsonify(result=True)

def truncate(val, count=80):
    if len(val) > count:
        return '%s...' % val[:count]
    return val
