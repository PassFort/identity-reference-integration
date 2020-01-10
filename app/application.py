import os

from flask import Flask, send_file, request, jsonify

from app.api import RunCheckResponse, RunCheckRequest, validate_models
from app.http_signature import HTTPSignatureAuth
from app.startup import integration_key_store

# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = Flask(__name__)

auth = HTTPSignatureAuth()


@auth.resolve_key
def resolve_key(key_id, algorithm):
    return integration_key_store.get((key_id, algorithm))


@app.route('/')
def index():
    return send_file('../static/metadata.json')


@app.route('/config')
@auth.login_required
def get_config():
    return send_file('../static/config.json')


@app.route('/checks', methods=['POST'])
@auth.login_required
@validate_models(RunCheckRequest, RunCheckResponse)
def run_check():
    # TODO: Implement check runner
    return RunCheckResponse()
