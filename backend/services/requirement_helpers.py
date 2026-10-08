import json
from datetime import datetime, timezone
from flask import g, send_file
from admin_dashboard import record_activity
from app import REQUIREMENT_TYPES, REVIEW_STATUSES, RISK_LEVELS, get_connection
from services.responses import response_payload

def _masked_email(email):
    if not isinstance(email, str):
        return '<invalid>'
    normalized_email = email.strip().lower()
    local, separator, domain = normalized_email.partition('@')
    if not separator or not local or (not domain):
        return '<invalid>'
    return f'{local[0]}***@{domain}'

def _utc_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

def _inserted_id(connection, cursor):
    if connection.dialect == 'postgres':
        return cursor.fetchone()['id']
    return cursor.lastrowid

def _public_user(user, connection=None):
    # Admin permissions are static; other roles must use fresh database values.
    if user['role'] == 'admin':
        from admin_dashboard import PERMISSIONS
        permissions = list(PERMISSIONS)
    else:
        owns_connection = connection is None
        if owns_connection:
            connection = get_connection()
        try:
            permissions = [row['permission'] for row in connection.execute(
                'SELECT permission FROM role_permissions WHERE role=? AND enabled=1',
                (user['role'],),
            )]
        finally:
            if owns_connection:
                connection.close()
    return {'permissions': permissions, 'id': user['id'], 'name': user['name'],
            'email': user['email'], 'role': user['role'], 'created_at': user['created_at']}


def _get_requirement_detail(connection, requirement_id):
    row = connection.execute('SELECT r.*, u.name AS assigned_reviewer FROM requirements r LEFT JOIN users u ON u.id=r.assigned_reviewer_user_id WHERE r.id = ?', (requirement_id,)).fetchone()
    if row is None:
        return None
    requirement = dict(row)
    requirement['needs_confirmation'] = bool(requirement['needs_confirmation'])
    try:
        analysis = json.loads(requirement.get('analysis_summary') or '{}')
        requirement['analysis_summary'] = analysis if isinstance(analysis, dict) else {}
    except (ValueError, TypeError):
        requirement['analysis_summary'] = {}
    if requirement.get('reviewed_by_user_id') is not None:
        reviewer = connection.execute('SELECT name FROM users WHERE id = ?', (requirement['reviewed_by_user_id'],)).fetchone()
        requirement['reviewed_by_name'] = reviewer['name'] if reviewer else None
    else:
        requirement['reviewed_by_name'] = None
    requirement['acceptance_criteria'] = [dict(item) for item in connection.execute('SELECT criterion_code, description, source, needs_confirmation, introduced_values FROM requirement_acceptance_criteria WHERE requirement_id = ? ORDER BY id', (requirement_id,)).fetchall()]
    for criterion in requirement['acceptance_criteria']:
        criterion['needs_confirmation'] = bool(criterion['needs_confirmation'])
        criterion['introduced_values'] = json.loads(criterion['introduced_values'])
    scenarios = connection.execute('SELECT id, scenario_code, category, title, preconditions, test_steps, expected_result, source, needs_confirmation, introduced_values, assumption_reasons FROM test_scenarios WHERE requirement_id = ? ORDER BY id', (requirement_id,)).fetchall()
    requirement['test_scenarios'] = []
    for scenario_row in scenarios:
        scenario = dict(scenario_row)
        scenario['preconditions'] = json.loads(scenario['preconditions'])
        scenario['test_steps'] = json.loads(scenario['test_steps'])
        scenario['needs_confirmation'] = bool(scenario['needs_confirmation'])
        scenario['introduced_values'] = json.loads(scenario['introduced_values'])
        scenario['assumption_reasons'] = json.loads(scenario['assumption_reasons'])
        requirement['test_scenarios'].append(scenario)
    assumptions = connection.execute('SELECT assumption_code, description, source, needs_confirmation, introduced_values FROM requirement_assumptions WHERE requirement_id = ? ORDER BY id', (requirement_id,)).fetchall()
    requirement['assumptions'] = [dict(item) for item in assumptions]
    for assumption in requirement['assumptions']:
        assumption['needs_confirmation'] = bool(assumption['needs_confirmation'])
        assumption['introduced_values'] = json.loads(assumption['introduced_values'])
    return requirement

def _project_report_summary(connection):
    rows = connection.execute('SELECT review_status, risk_level, requirement_type, risk_score FROM requirements').fetchall()
    review_counts = {status: 0 for status in REVIEW_STATUSES}
    risk_counts = {level: 0 for level in RISK_LEVELS}
    risk_counts['Unscored'] = 0
    type_counts = {requirement_type: 0 for requirement_type in REQUIREMENT_TYPES}
    risk_scores = []
    for row in rows:
        review_counts[row['review_status']] = review_counts.get(row['review_status'], 0) + 1
        risk_level = row['risk_level'] or 'Unscored'
        risk_counts[risk_level] = risk_counts.get(risk_level, 0) + 1
        type_counts[row['requirement_type']] = type_counts.get(row['requirement_type'], 0) + 1
        if row['risk_score'] is not None:
            risk_scores.append(row['risk_score'])
    total_requirements = len(rows)
    total_test_scenarios = connection.execute('SELECT COUNT(*) FROM test_scenarios').fetchone()[0]
    traceable_requirement_count = connection.execute('SELECT COUNT(*) FROM requirements AS requirement WHERE EXISTS (SELECT 1 FROM requirement_acceptance_criteria AS criterion WHERE criterion.requirement_id = requirement.id) AND EXISTS (SELECT 1 FROM test_scenarios AS scenario WHERE scenario.requirement_id = requirement.id)').fetchone()[0]
    high_attention_requirements = [dict(row) for row in connection.execute("SELECT id, title, risk_score, risk_level, review_status FROM requirements WHERE risk_level IN ('High', 'Critical') OR review_status = 'Needs Revision' ORDER BY CASE risk_level WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 ELSE 2 END, risk_score DESC, COALESCE(updated_at, created_at) DESC, id DESC").fetchall()]
    return {'total_requirements': total_requirements, 'review_counts': review_counts, 'risk_counts': risk_counts, 'type_counts': type_counts, 'average_risk_score': round(sum(risk_scores) / len(risk_scores), 1) if risk_scores else 0, 'total_test_scenarios': total_test_scenarios, 'traceable_requirement_count': traceable_requirement_count, 'traceability_coverage_percent': round(traceable_requirement_count * 100 / total_requirements, 1) if total_requirements else 0, 'high_attention_requirements': high_attention_requirements}

def _download_response(file_stream, filename, mimetype):
    response = send_file(file_stream, mimetype=mimetype, as_attachment=True, download_name=filename, max_age=0)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

def _save_review(requirement_id, data, required_fields=()):
    if not isinstance(data, dict):
        return (response_payload(error='Send a JSON object with review details.'), 400)
    if not any((field in data for field in ('review_status', 'reviewer_notes'))):
        return (response_payload(error='Provide a review status or reviewer notes.'), 400)
    if any((field not in data for field in required_fields)):
        return (response_payload(error='Include the required review field.'), 400)
    updates = []
    values = []
    if 'review_status' in data:
        review_status = data['review_status']
        if not isinstance(review_status, str) or review_status not in REVIEW_STATUSES:
            return (response_payload(error='Choose a valid review status.'), 400)
        updates.append('review_status = ?')
        values.append(review_status)
        updates.extend(('source = ?', 'needs_confirmation = 0'))
        values.append('confirmed' if review_status == 'Approved' else 'original')
    if 'reviewer_notes' in data:
        reviewer_notes = data['reviewer_notes']
        if not isinstance(reviewer_notes, str):
            return (response_payload(error='Reviewer notes must be text.'), 400)
        updates.append('reviewer_notes = ?')
        values.append(reviewer_notes.strip())
    review_timestamp = _utc_timestamp()
    updates.extend(('reviewed_by_user_id = ?', 'reviewed_at = ?'))
    values.extend((g.current_user['id'], review_timestamp))
    updates.append('updated_at = ?')
    values.append(review_timestamp)
    values.append(requirement_id)
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(f"UPDATE requirements SET {', '.join(updates)} WHERE id = ?", values)
            if cursor.rowcount == 0:
                return (response_payload(error='Requirement not found.'), 404)
            if 'review_status' in data:
                _update_related_confirmation(connection, requirement_id, approved=review_status == 'Approved')
            record_activity(connection, g.current_user, 'review_updated', 'requirement', requirement_id, f"Reviewed REQ-{requirement_id}: {data.get('review_status', 'notes updated')}")
            requirement = _get_requirement_detail(connection, requirement_id)
    finally:
        connection.close()
    return response_payload(requirement=requirement)

def _update_related_confirmation(connection, requirement_id, approved):
    if approved:
        for table in ('requirement_acceptance_criteria', 'test_scenarios', 'requirement_assumptions'):
            connection.execute(f'UPDATE {table} SET needs_confirmation = 0 WHERE requirement_id = ?', (requirement_id,))
        return
    criteria = connection.execute('SELECT id, source, introduced_values FROM requirement_acceptance_criteria WHERE requirement_id = ?', (requirement_id,)).fetchall()
    for item in criteria:
        source = item['source']
        needs_confirmation = source in {'ai_assumption', 'confirmed'} or bool(json.loads(item['introduced_values']))
        if source == 'confirmed':
            source = 'ai_suggestion'
        connection.execute('UPDATE requirement_acceptance_criteria SET source = ?, needs_confirmation = ? WHERE id = ?', (source, int(needs_confirmation), item['id']))
    scenarios = connection.execute('SELECT id, source, introduced_values, assumption_reasons FROM test_scenarios WHERE requirement_id = ?', (requirement_id,)).fetchall()
    for item in scenarios:
        source = item['source']
        needs_confirmation = source in {'ai_assumption', 'confirmed'} or bool(json.loads(item['introduced_values'])) or bool(json.loads(item['assumption_reasons']))
        if source == 'confirmed':
            source = 'ai_suggestion'
        connection.execute('UPDATE test_scenarios SET source = ?, needs_confirmation = ? WHERE id = ?', (source, int(needs_confirmation), item['id']))
    connection.execute('UPDATE requirement_assumptions SET needs_confirmation = 1 WHERE requirement_id = ?', (requirement_id,))
