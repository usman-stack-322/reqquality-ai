import json
from flask import g
from admin_dashboard import record_activity
from app import REQUIREMENT_TYPES, PRIORITIES, get_connection
from services.requirement_helpers import _utc_timestamp, _inserted_id, _get_requirement_detail, _save_review
from validators.requirement_validator import _validate_analysis_payload
from services.responses import response_payload

def create_requirement(payload):
    data = payload
    if not isinstance(data, dict):
        return (response_payload(error='Send a JSON object with requirement details.'), 400)
    title = data.get('title')
    description = data.get('description')
    requirement_type = data.get('requirement_type')
    priority = data.get('user_priority', data.get('priority'))
    analysis = data.get('analysis')
    if not isinstance(title, str) or not title.strip():
        return (response_payload(error='Please enter a requirement title.'), 400)
    if not isinstance(description, str) or not description.strip():
        return (response_payload(error='Please enter a requirement description.'), 400)
    if not isinstance(requirement_type, str) or requirement_type not in REQUIREMENT_TYPES:
        return (response_payload(error='Choose a valid requirement type.'), 400)
    if not isinstance(priority, str) or priority not in PRIORITIES:
        return (response_payload(error='Choose a valid priority.'), 400)
    validation_error = _validate_analysis_payload(analysis)
    if validation_error:
        return (response_payload(error=validation_error), 400)
    analysis = analysis or {}
    acceptance_criteria = [value.strip() for value in analysis.get('acceptance_criteria', []) if value.strip()]
    labeled_analysis = analysis.get('labeled_analysis', {})
    criteria_details = {item['text'].strip(): item for item in labeled_analysis.get('acceptance_criteria', []) if isinstance(item, dict) and isinstance(item.get('text'), str)}
    assumption_details = labeled_analysis.get('assumptions', [])
    if not assumption_details:
        assumption_details = [{'text': value, 'source': 'ai_assumption', 'needs_confirmation': True, 'introduced_values': []} for value in analysis.get('assumptions', [])]
    scenarios = analysis.get('test_scenarios', [])
    analysis_summary = {field: analysis[field] for field in ('ambiguity_issues', 'missing_information', 'testability_issues', 'assumptions', 'edge_cases', 'improved_requirement', 'labeled_analysis', 'analysis_mode', 'llm_status') if field in analysis}
    connection = get_connection()
    try:
        with connection:
            insert_statement = 'INSERT INTO requirements (title, description, requirement_type, priority, user_priority, suggested_priority, risk_score, risk_level, updated_at, created_by_user_id, analysis_summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
            if connection.dialect == 'postgres':
                insert_statement += ' RETURNING id'
            cursor = connection.execute(insert_statement, (title.strip(), description.strip(), requirement_type, priority, priority, analysis.get('suggested_priority'), analysis.get('risk_score'), analysis.get('risk_level'), _utc_timestamp(), g.current_user['id'], json.dumps(analysis_summary, ensure_ascii=True)))
            requirement_id = _inserted_id(connection, cursor)
            connection.executemany('INSERT INTO requirement_acceptance_criteria (requirement_id, criterion_code, description, source, needs_confirmation, introduced_values) VALUES (?, ?, ?, ?, ?, ?)', [(requirement_id, f'AC-{index:03d}', criterion, criteria_details.get(criterion, {}).get('source', 'rule_based'), int(criteria_details.get(criterion, {}).get('needs_confirmation', False)), json.dumps(criteria_details.get(criterion, {}).get('introduced_values', []))) for index, criterion in enumerate(acceptance_criteria, start=1)])
            scenario_records = []
            for index, scenario in enumerate(scenarios, start=1):
                scenario_code = scenario.get('id') or f'SC-{index:03d}'
                scenario_records.append((requirement_id, scenario_code, scenario['category'], scenario['title'].strip(), json.dumps(scenario.get('preconditions', [])), json.dumps(scenario.get('test_steps', [])), scenario['expected_result'].strip(), scenario.get('source', 'rule_based'), int(scenario.get('needs_confirmation', False)), json.dumps(scenario.get('introduced_values', [])), json.dumps(scenario.get('assumption_reasons', []))))
            connection.executemany('INSERT INTO test_scenarios (requirement_id, scenario_code, category, title, preconditions, test_steps, expected_result, source, needs_confirmation, introduced_values, assumption_reasons) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', scenario_records)
            connection.executemany('INSERT INTO requirement_assumptions (requirement_id, assumption_code, description, source, needs_confirmation, introduced_values) VALUES (?, ?, ?, ?, ?, ?)', [(requirement_id, f'AS-{index:03d}', item['text'].strip(), 'ai_assumption', int(item.get('needs_confirmation', True)), json.dumps(item.get('introduced_values', []))) for index, item in enumerate(assumption_details, start=1) if isinstance(item, dict) and isinstance(item.get('text'), str) and item['text'].strip()])
            record_activity(connection, g.current_user, 'requirement_created', 'requirement', requirement_id, f'Created REQ-{requirement_id}')
            requirement = _get_requirement_detail(connection, requirement_id)
    finally:
        connection.close()
    return (response_payload(requirement=requirement), 201)

def list_requirements():
    connection = get_connection()
    try:
        rows = connection.execute('SELECT * FROM requirements ORDER BY id DESC').fetchall()
    finally:
        connection.close()
    return response_payload(requirements=[dict(row) for row in rows])

def get_requirement(requirement_id):
    connection = get_connection()
    try:
        requirement = _get_requirement_detail(connection, requirement_id)
    finally:
        connection.close()
    if requirement is None:
        return (response_payload(error='Requirement not found.'), 404)
    return response_payload(requirement=requirement)

def update_review(requirement_id, headers):
    return _save_review(requirement_id, headers)

def update_review_status(requirement_id, headers):
    return _save_review(requirement_id, headers, required_fields=('review_status',))

def update_reviewer_notes(requirement_id, headers):
    return _save_review(requirement_id, headers, required_fields=('reviewer_notes',))
