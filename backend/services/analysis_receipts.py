"""Authenticate generated results without trusting provenance supplied by a browser.

Receipts are user/input-bound and contain no credentials. Historical stored results
remain readable; only new acceptance requires a receipt from the analysis endpoint.
"""
import hashlib
import hmac
import json
from flask import current_app, g


def analysis_input(data):
    from analyzers.llm_analyzer import generation_configuration
    return {**{key: data[key].strip() for key in ('title', 'description', 'requirement_type', 'priority')},
            'clarifications': data.get('clarifications', '').strip(),
            'project_id': data.get('project_id', 'current'),
            'project_context': data.get('project_context', ''),
            'context_revision': data.get('context_revision', 1),
            'requirement_id': data.get('requirement_id'),
            'requirement_revision': data.get('requirement_revision', 1),
            'generation_config': data.get('generation_config', generation_configuration())}


def bound_input(connection, data, requirement=None, project=None):
    from services.project_service import current_project
    from analyzers.llm_analyzer import generation_configuration
    project = project or current_project(connection)
    return analysis_input({**data, 'project_id': project['id'], 'project_context': project['context'],
                           'context_revision': project['revision'],
                           'requirement_id': requirement['id'] if requirement is not None else None,
                           'requirement_revision': requirement['revision'] if requirement is not None else 1,
                           'generation_config': generation_configuration()})


def input_hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def edited_draft(analysis, edits):
    """Edits never alter the signed provider result or its receipt."""
    from flask import abort
    from analyzers.llm_analyzer import REQUIRED_FIELDS, _validate_analysis
    if edits is None:
        return analysis
    if not isinstance(edits, dict) or any(key not in REQUIRED_FIELDS for key in edits):
        abort(400, description='Edit only analysis draft fields.')
    draft = _validate_analysis({**analysis, **edits})
    if draft is None:
        abort(400, description='The edited analysis draft is incomplete or invalid.')
    labels = dict(analysis.get('labeled_analysis', {}))
    for key, value in edits.items():
        def human(text):
            return dict(text=text, source='original', needs_confirmation=True, introduced_values=[])
        labels[key] = [human(v) for v in value] if isinstance(value, list) and key != 'test_scenarios' else human(value) if isinstance(value, str) else []
    return {**analysis, **draft, 'human_edits': edits, 'labeled_analysis': labels}


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
