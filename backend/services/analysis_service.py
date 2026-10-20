from analyzers.ai_analyzer import analyze_ai
from app import REQUIREMENT_TYPES, PRIORITIES
from services.responses import response_payload

def analyze_requirement_endpoint(payload):
    data = payload
    if not isinstance(data, dict):
        return (response_payload(error='Send a JSON object with requirement details.'), 400)
    title = data.get('title')
    description = data.get('description')
    requirement_type = data.get('requirement_type')
    priority = data.get('priority')
    if not isinstance(title, str) or not title.strip():
        return (response_payload(error='Please enter a requirement title.'), 400)
    if not isinstance(description, str) or not description.strip():
        return (response_payload(error='Please enter a requirement description.'), 400)
    if not isinstance(requirement_type, str) or requirement_type not in REQUIREMENT_TYPES:
        return (response_payload(error='Choose a valid requirement type.'), 400)
    if not isinstance(priority, str) or priority not in PRIORITIES:
        return (response_payload(error='Choose a valid priority.'), 400)
    from validators.requirement_validator import validate_requirement_text
    error = validate_requirement_text(title, description)
    if error:
        return response_payload(error=error), 400
    if not isinstance(data.get('clarifications', ''), str) or len(data.get('clarifications', '')) > 20000:
        return response_payload(error='Clarification answers must be text of at most 20,000 characters.'), 400
    from services.analysis_requests import run_analysis
    from services.analysis_receipts import bound_input, sign_analysis
    from app import get_connection
    import json
    from flask import abort, g
    c = get_connection()
    try:
        requirement = None
        if data.get('requirement_id') is not None:
            if type(data['requirement_id']) is not int or type(data.get('requirement_revision')) is not int:
                abort(400, description='Provide the saved requirement ID and revision.')
            requirement = c.execute("SELECT * FROM requirements WHERE id=? AND project_id='current'", (data['requirement_id'],)).fetchone()
            if requirement is None:
                abort(404)
            if requirement['revision'] != data['requirement_revision']:
                abort(409, description='Requirement changed. Reload before analyzing.')
            try:
                summary = json.loads(requirement['analysis_summary'])
                summary = summary if isinstance(summary, dict) else {}
            except (TypeError, ValueError):
                summary = {}
            expected = dict(title=requirement['title'], description=requirement['description'], requirement_type=requirement['requirement_type'], priority=requirement['user_priority'], clarifications=summary.get('clarifications', ''))
            if any(data.get(key, '').strip() != value for key, value in expected.items()):
                abort(409, description='Save requirement text and clarification edits before analysis.')
        inputs = bound_input(c, data, requirement)
        if requirement is not None:
            from services.analysis_receipts import input_hash, verify_analysis
            saved = c.execute('SELECT result FROM requirement_analysis_drafts WHERE requirement_id=? AND requirement_revision=? AND user_id=? AND input_hash=?',
                              (requirement['id'],requirement['revision'],g.current_user['id'],input_hash(inputs))).fetchone()
            if saved:
                proposal = json.loads(saved['result'])
                if verify_analysis(proposal, inputs):
                    return response_payload(proposal), 200
    finally:
        c.close()
    result = run_analysis(inputs, lambda: sign_analysis(analyze_ai(**inputs), inputs))
    if result.get('status') == 'completed' and requirement is not None:
        from services.project_service import lock_project
        from services.analysis_receipts import input_hash
        from services.requirement_helpers import _utc_timestamp
        c = get_connection()
        try:
            with c:
                project = lock_project(c)
                latest = c.execute('SELECT * FROM requirements WHERE id=?', (requirement['id'],)).fetchone()
                if latest['revision'] != inputs['requirement_revision'] or bound_input(c, data, latest, project) != inputs:
                    return response_payload(status='failed', code='stale_analysis', retryable=True, error='Requirement or context changed during analysis. Reload and retry.'), 409
                c.execute('INSERT INTO requirement_analysis_drafts(requirement_id,project_id,requirement_revision,user_id,input_hash,result,created_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(requirement_id,requirement_revision,user_id,input_hash) DO NOTHING',
                          (latest['id'], 'current', latest['revision'], g.current_user['id'], input_hash(inputs), json.dumps(result), _utc_timestamp()))
        finally:
            c.close()
    return response_payload(result), (200 if result.get('status') == 'completed' else 503)
