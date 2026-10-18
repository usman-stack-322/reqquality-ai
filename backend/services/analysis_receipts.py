"""Authenticate generated results without trusting provenance supplied by a browser.

Receipts are user/input-bound and contain no credentials. Historical stored results
remain readable; only new acceptance requires a receipt from the analysis endpoint.
"""
import hashlib
import hmac
import json
from flask import current_app, g


def analysis_input(data):
    return {**{key: data[key].strip() for key in ('title', 'description', 'requirement_type', 'priority')},
            'clarifications': data.get('clarifications', '').strip()}


def _signature(result):
    payload = {'purpose': 'reqquality-analysis', 'user_id': g.current_user['id'],
               'result': {key: value for key, value in result.items() if key != 'analysis_receipt'}}
    secret = current_app.config['JWT_SECRET_KEY']
    if isinstance(secret, str):
        secret = secret.encode('utf-8')
    return hmac.new(secret, json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode(), hashlib.sha256).hexdigest()


def sign_analysis(result, data):
    if result.get('status') == 'completed':
        result['analysis_input'] = analysis_input(data)
        result['analysis_receipt'] = _signature(result)
    return result


def verify_analysis(result, data):
    receipt = result.get('analysis_receipt')
    return (isinstance(receipt, str) and len(receipt) == 64
            and result.get('analysis_input') == analysis_input(data)
            and hmac.compare_digest(receipt, _signature(result)))
