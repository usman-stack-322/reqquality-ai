import json
import hashlib
import re
from flask import g, request
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
    from validators.requirement_validator import validate_requirement_text
    validation_error = validate_requirement_text(title, description) or _validate_analysis_payload(analysis)
    if validation_error:
        return (response_payload(error=validation_error), 400)
    if analysis:
        from analyzers.llm_analyzer import _validate_analysis
        from services.analysis_receipts import verify_analysis, bound_input
        receipt_connection = get_connection()
        try:
            verified = verify_analysis(analysis, bound_input(receipt_connection, dict(title=title, description=description, requirement_type=requirement_type, priority=priority)))
        finally:
            receipt_connection.close()
        if analysis.get('analysis_mode') != 'ai_only' or analysis.get('status') != 'completed' or _validate_analysis(analysis) is None or not verified:
            return response_payload(error='Save a draft without analysis, or provide a complete AI analysis.'), 400
    provider_analysis = analysis
    if analysis:
        from services.analysis_receipts import edited_draft
        analysis = edited_draft(analysis, data.get('analysis_edits'))
    analysis = analysis or {}
    acceptance_criteria = [value.strip() for value in analysis.get('acceptance_criteria', []) if value.strip()]
    labeled_analysis = analysis.get('labeled_analysis', {})
    criteria_details = {item['text'].strip(): item for item in labeled_analysis.get('acceptance_criteria', []) if isinstance(item, dict) and isinstance(item.get('text'), str)}
    assumption_details = labeled_analysis.get('assumptions', [])
    if not assumption_details:
        assumption_details = [{'text': value, 'source': 'ai_assumption', 'needs_confirmation': True, 'introduced_values': []} for value in analysis.get('assumptions', [])]
    scenarios = analysis.get('test_scenarios', [])
    analysis_summary = {field: analysis[field] for field in ('ambiguity_issues', 'conflict_issues', 'missing_information', 'clarification_questions', 'testability_issues', 'assumptions', 'edge_cases', 'improved_requirement', 'labeled_analysis', 'analysis_mode', 'llm_status', 'analysis_version', 'model', 'risk_reasons', 'priority_reasons', 'suggested_requirement_type', 'type_explanation', 'analysis_input', 'human_edits') if field in analysis}
    submission_key = request.headers.get('Idempotency-Key')
    if submission_key is not None and not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', submission_key):
        return response_payload(error='Invalid submission key.'), 400
    input_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    connection = get_connection()
    try:
        with connection:
            if provider_analysis:
                from services.project_service import lock_project
                from services.analysis_receipts import bound_input, verify_analysis
                project = lock_project(connection)
                if not verify_analysis(provider_analysis, bound_input(connection, dict(title=title,description=description,requirement_type=requirement_type,priority=priority), project=project)):
                    return response_payload(error='Project context or generation configuration changed. Analyze again.'), 409
            if submission_key:
                claimed = connection.execute('INSERT INTO requirement_submissions(user_id,request_key,input_hash) VALUES(?,?,?) ON CONFLICT(user_id,request_key) DO NOTHING', (g.current_user['id'],submission_key,input_hash))
                if claimed.rowcount == 0:
                    prior = connection.execute('SELECT input_hash,requirement_id FROM requirement_submissions WHERE user_id=? AND request_key=?',(g.current_user['id'],submission_key)).fetchone()
                    if prior['input_hash'] != input_hash:
                        return response_payload(error='This submission key belongs to different input. Start a new save.'), 409
                    return response_payload(requirement=_get_requirement_detail(connection,prior['requirement_id'])), 201
            insert_statement = "INSERT INTO requirements (title, description, requirement_type, priority, user_priority, suggested_priority, risk_score, risk_level, updated_at, created_by_user_id, analysis_summary, review_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Draft')"
            if connection.dialect == 'postgres':
                insert_statement += ' RETURNING id'
            cursor = connection.execute(insert_statement, (title.strip(), description.strip(), requirement_type, priority, priority, analysis.get('suggested_priority'), analysis.get('risk_score'), analysis.get('risk_level'), _utc_timestamp(), g.current_user['id'], json.dumps(analysis_summary, ensure_ascii=True)))
            requirement_id = _inserted_id(connection, cursor)
            if provider_analysis:
                from services.analysis_receipts import input_hash as analysis_input_hash
                connection.execute('INSERT INTO requirement_analysis_drafts(requirement_id,project_id,requirement_revision,user_id,input_hash,result,created_at) VALUES(?,?,?,?,?,?,?)',
                                   (requirement_id, 'current', 1, g.current_user['id'], analysis_input_hash(provider_analysis['analysis_input']), json.dumps(provider_analysis), _utc_timestamp()))
            connection.executemany('INSERT INTO requirement_acceptance_criteria (requirement_id, criterion_code, description, source, needs_confirmation, introduced_values) VALUES (?, ?, ?, ?, ?, ?)', [(requirement_id, f'AC-{index:03d}', criterion, criteria_details.get(criterion, {}).get('source', 'ai_suggestion'), int(criteria_details.get(criterion, {}).get('needs_confirmation', True)), json.dumps(criteria_details.get(criterion, {}).get('introduced_values', []))) for index, criterion in enumerate(acceptance_criteria, start=1)])
            scenario_records = []
            for index, scenario in enumerate(scenarios, start=1):
                if 'test_scenarios' in analysis.get('human_edits', {}):
                    scenario = {**scenario, 'source':'original', 'needs_confirmation':True}
                scenario_code = scenario.get('id') or f'SC-{index:03d}'
                scenario_records.append((requirement_id, scenario_code, scenario['category'], scenario['title'].strip(), json.dumps(scenario.get('preconditions', [])), json.dumps(scenario.get('test_steps', [])), scenario['expected_result'].strip(), scenario.get('source', 'ai_suggestion'), int(scenario.get('needs_confirmation', True)), json.dumps(scenario.get('introduced_values', [])), json.dumps(scenario.get('assumption_reasons', [])), json.dumps(scenario.get('criterion_codes', []))))
            connection.executemany('INSERT INTO test_scenarios (requirement_id, scenario_code, category, title, preconditions, test_steps, expected_result, source, needs_confirmation, introduced_values, assumption_reasons, criterion_codes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', scenario_records)
            from services.case_service import register_generated_cases
            register_generated_cases(connection,requirement_id)
            connection.executemany('INSERT INTO requirement_assumptions (requirement_id, assumption_code, description, source, needs_confirmation, introduced_values) VALUES (?, ?, ?, ?, ?, ?)', [(requirement_id, f'AS-{index:03d}', item['text'].strip(), 'ai_assumption', int(item.get('needs_confirmation', True)), json.dumps(item.get('introduced_values', []))) for index, item in enumerate(assumption_details, start=1) if isinstance(item, dict) and isinstance(item.get('text'), str) and item['text'].strip()])
            record_activity(connection, g.current_user, 'requirement_created', 'requirement', requirement_id, f'Created REQ-{requirement_id}')
            from services.workflow_service import snapshot
            from services.requirement_helpers import _get_requirement_history
            requirement = _get_requirement_detail(connection, requirement_id, include_history=False)
            snapshot(connection, requirement_id, 'draft_created', requirement)
            if submission_key:
                connection.execute('UPDATE requirement_submissions SET requirement_id=? WHERE user_id=? AND request_key=?',(requirement_id,g.current_user['id'],submission_key))
            requirement['history'] = _get_requirement_history(connection, requirement_id)
    finally:
        connection.close()
    return (response_payload(requirement=requirement), 201)

def list_requirements():
    from flask import request
    # Opt-in summary preserves the existing full API for other clients.
    fields = ('id, title, requirement_type, priority, user_priority, suggested_priority, '
              'risk_score, risk_level, review_status, created_at, updated_at, content_revision, reviewed_content_revision') if request.args.get('view') == 'summary' else '*'
    try:
        page = max(1, int(request.args.get('page', '1')))
        size = min(100, max(1, int(request.args.get('page_size', '50'))))
    except ValueError:
        return response_payload(error='Invalid pagination.'), 400
    clauses, values = [], []
    choices = {'status': ('review_status', {'Draft','Ready for Review','Pending','In Review','Approved','Needs Revision'}),
               'risk': ('risk_level', {'Low','Medium','High','Critical'}),
               'priority': ('user_priority', PRIORITIES), 'type': ('requirement_type', REQUIREMENT_TYPES)}
    for key, (column, valid) in choices.items():
        value = request.args.get(key)
        if value:
            if value not in valid:
                return response_payload(error='Invalid queue filter.'), 400
            if key=='status' and value=='Pending':
                clauses.append("(review_status IN ('Pending','Draft','Ready for Review') OR (review_status='Approved' AND (reviewed_content_revision IS NULL OR reviewed_content_revision!=content_revision)))")
            else:
                clauses.append(f'{column}=?')
                values.append(value)
                if key=='status' and value=='Approved': clauses.append('reviewed_content_revision=content_revision')
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    connection = get_connection()
    try:
        with connection.autocommit_reads():
            total = connection.execute('SELECT COUNT(*) FROM requirements'+where, values).fetchone()[0]
            rows = connection.execute(f'SELECT {fields} FROM requirements'+where+' ORDER BY id DESC LIMIT ? OFFSET ?', [*values,size,(page-1)*size]).fetchall()
    finally:
        connection.close()
    from services.integrated_service import review_status
    records=[dict(row) for row in rows]
    for row in records: row['sqa_review_status']=review_status(row)
    return response_payload(requirements=records, total=total, page=page, page_size=size)


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
