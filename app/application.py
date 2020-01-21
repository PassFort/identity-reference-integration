import json
import os
import re

from dataclasses import dataclass
from typing import Optional, List, Tuple

from flask import Flask, send_file, request, abort, Response

from app.api import RunCheckResponse, RunCheckRequest, validate_models, Error, DatedAddress, ErrorType, Field, Address, \
    DemoResultType
from app.http_signature import HTTPSignatureAuth
from app.startup import integration_key_store

# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = Flask(__name__)

auth = HTTPSignatureAuth()

SUPPORTED_COUNTRIES = ['GBR', 'USA', 'CAN', 'NLD']


@dataclass
class CheckInput:
    current_address: Address
    dob: Optional[str]
    given_names: List[str]
    family_name: str


@app.before_request
def pre_request_logging():
    request_data = '\n' + request.data.decode('utf8')
    request_data = request_data.replace('\n', '\n    ')

    app.logger.info(f'{request.method} {request.url}{request_data}')


@app.after_request
def post_request_logging(response):
    if response.direct_passthrough:
        response_data = '\n(direct pass-through)'
    else:
        response_data = '\n' + response.data.decode('utf8')
    response_data = response_data.replace('\n', '\n    ')

    app.logger.info(f'{response.status} {request.url}{response_data}')
    return response


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


def _sanitize_filename(value: str, program=re.compile('^[a-zA-Z_]+$')):
    if not program.match(value):
        abort(Response('Invalid demo request'), status=400)
    return value


def _run_demo_check(check_input: CheckInput, demo_result: str) -> RunCheckResponse:
    current_address = check_input.current_address

    def _try_load_demo_result(name: str):
        filename = f'../static/demo_results/{_sanitize_filename(name)}.json'

        try:
            # Load file relative to current script
            with open(os.path.join(os.path.dirname(__file__), filename), 'r') as file:
                demo_response = RunCheckResponse().import_data(json.load(file), apply_defaults=True)
        except FileNotFoundError:
            return None

        check_output = demo_response.check_output

        if check_output is not None and check_output.address_history is not None and current_address is not None:
            demo_response.check_output.address_history = [
                DatedAddress(address=current_address)
            ]

        return demo_response

    # Default to no matches if we could return any result
    if demo_result == DemoResultType.ANY:
        demo_result = DemoResultType.NO_MATCHES

    return _try_load_demo_result(f'{current_address.country}_{demo_result}') or \
        _try_load_demo_result(f'OTHER_{demo_result}') or \
        _try_load_demo_result('UNSUPPORTED_DEMO_RESULT')


def _extract_input(req: RunCheckRequest) -> Tuple[List[Error], Optional[CheckInput]]:
    errors = []

    # Extract address
    # TODO: Validate required address fields
    current_address = req.check_input.get_current_address()
    if current_address is None:
        errors.append(Error.missing_required_field(Field.ADDRESS_HISTORY))

    # Extract DOB
    dob = req.check_input.get_dob()
    if dob is None and req.provider_config.require_dob:
        errors.append(Error.missing_required_field(Field.DOB))

    # Extract given names
    given_names = req.check_input.get_given_names()
    if given_names is None:
        errors.append(Error.missing_required_field(Field.GIVEN_NAMES))

    # Extract family name
    family_name = req.check_input.get_family_name()
    if family_name is None:
        errors.append(Error.missing_required_field(Field.FAMILY_NAME))

    if errors:
        return errors, None
    else:
        return [], CheckInput(
            current_address=current_address,
            dob=dob,
            given_names=given_names,
            family_name=family_name
        )


@app.route('/checks', methods=['POST'])
@auth.login_required
@validate_models
def run_check(req: RunCheckRequest) -> RunCheckResponse:
    errors, check_input = _extract_input(req)
    if errors:
        return RunCheckResponse.error(errors)

    country = check_input.current_address.country
    if country not in SUPPORTED_COUNTRIES:
        return RunCheckResponse.error([Error.unsupported_country()])

    if req.demo_result is not None:
        return _run_demo_check(check_input, req.demo_result)

    return RunCheckResponse.error([Error({
        'type': ErrorType.PROVIDER_MESSAGE,
        'message': 'Live checks are not supported',
    })])
