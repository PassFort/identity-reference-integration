import base64
import os
import time

from email.utils import formatdate
from uuid import uuid4


def test_run_check_protected(session, auth):
    # Should require authentication
    r = session.post('http://app/checks', json={})
    assert r.status_code == 401

    # Should require correct key
    bad_key = os.urandom(256)
    r = session.post('http://app/checks', json={}, auth=auth(key=bad_key))
    assert r.status_code == 401

    # Should require '(request-target)' *and* 'date' headers to be signed
    r = session.post('http://app/checks', json={}, auth=auth(headers=['date']))
    assert r.status_code == 401

    # Should require 'date' header to be recent
    old_date = formatdate(time.time() - 120)
    r = session.post('http://app/checks', json={}, headers={'date': old_date}, auth=auth())
    assert r.status_code == 401

    # Should require digest to be correct
    bad_digest = base64.b64encode(os.urandom(256)).decode()
    r = session.post('http://app/checks', json={}, headers={'digest': f'SHA-256={bad_digest}'}, auth=auth())
    assert r.status_code == 401


def test_run_check_smoke(session, auth):
    r = session.post('http://app/checks', json={
        'id': str(uuid4()),
        'check_input': {
            'entity_type': 'INDIVIDUAL',
            'personal_details': {
                'name': {
                    'given_names': ['Henry'],
                    'family_name': 'Gnarglefoot'
                },
                'dob': '1990-01-01'
            },
            'address_history': [
                {
                    'address': {
                        'country': 'GBR'
                    }
                }
            ]
        },
        'commercial_relationship': 'DIRECT',
        'provider_config': {
            'require_dob': False,
            'mortality_check': True,
            'requires_address_on_all_matches': False,
            'run_original_address': False,
        },
        'demo_result': 'NO_MATCHES'
    }, auth=auth())
    assert r.status_code == 200
    assert r.headers['content-type'] == 'application/json'

    res = r.json()

    assert res['errors'] == []


def test_run_check_unsupported_country(session, auth):
    r = session.post('http://app/checks', json={
        'id': str(uuid4()),
        'check_input': {
            'entity_type': 'INDIVIDUAL',
            'personal_details': {
                'name': {
                    'given_names': ['Henry'],
                    'family_name': 'Gnarglefoot'
                },
                'dob': '1990-01-01'
            },
            'address_history': [
                {
                    'address': {
                        'country': 'FRA'
                    }
                }
            ]
        },
        'commercial_relationship': 'DIRECT',
        'provider_config': {
            'require_dob': False,
            'mortality_check': True,
            'requires_address_on_all_matches': False,
            'run_original_address': False,
        },
        'demo_result': 'NO_MATCHES'
    }, auth=auth())
    assert r.status_code == 200
    assert r.headers['content-type'] == 'application/json'

    res = r.json()

    assert res['errors'] == [{
        'type': 'INVALID_CHECK_INPUT',
        'sub_type': 'UNSUPPORTED_COUNTRY',
        'message': 'Country not supported.',
    }]


def test_run_check_unsupported_demo_result(session, auth):
    r = session.post('http://app/checks', json={
        'id': str(uuid4()),
        'check_input': {
            'entity_type': 'INDIVIDUAL',
            'personal_details': {
                'name': {
                    'given_names': ['Henry'],
                    'family_name': 'Gnarglefoot'
                },
                'dob': '1990-01-01'
            },
            'address_history': [
                {
                    'address': {
                        'country': 'GBR'
                    }
                }
            ]
        },
        'commercial_relationship': 'DIRECT',
        'provider_config': {
            'require_dob': False,
            'mortality_check': True,
            'requires_address_on_all_matches': False,
            'run_original_address': False,
        },
        'demo_result': 'NOT_A_REAL_DEMO_RESULT'
    }, auth=auth())
    assert r.status_code == 200
    assert r.headers['content-type'] == 'application/json'

    res = r.json()

    assert res['errors'] == [{
        'type': 'UNSUPPORTED_DEMO_RESULT',
        'message': 'Demo result is not supported.',
    }]


def test_run_check_invalid_credentials(session, auth):
    r = session.post('http://app/checks', json={
        'id': str(uuid4()),
        'check_input': {
            'entity_type': 'INDIVIDUAL',
            'personal_details': {
                'name': {
                    'given_names': ['Henry'],
                    'family_name': 'Gnarglefoot'
                },
                'dob': '1990-01-01'
            },
            'address_history': [
                {
                    'address': {
                        'country': 'GBR'
                    }
                }
            ]
        },
        'commercial_relationship': 'DIRECT',
        'provider_config': {
            'require_dob': False,
            'mortality_check': True,
            'requires_address_on_all_matches': False,
            'run_original_address': False,
        },
        'demo_result': 'ERROR_INVALID_CREDENTIALS'
    }, auth=auth())
    assert r.status_code == 200
    assert r.headers['content-type'] == 'application/json'

    res = r.json()

    assert res['errors'] == [{
        'type': 'INVALID_CREDENTIALS',
        'message': 'Username or password is invalid.',
    }]


