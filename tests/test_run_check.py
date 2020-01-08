import base64
import os
import time

from email.utils import formatdate


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
    r = session.post('http://app/checks', json={}, auth=auth())
    assert r.status_code == 200
    assert r.headers['content-type'] == 'application/json'

    _res = r.json()

