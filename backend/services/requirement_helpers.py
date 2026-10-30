import json
from datetime import datetime, timezone
from flask import g, send_file, has_request_context
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
    return {'project_access': bool(user['project_access']) if 'project_access' in user.keys() else True, 'permissions': permissions, 'id': user['id'], 'name': user['name'],
            'email': user['email'], 'role': user['role'], 'created_at': user['created_at']}


def _get_requirement_history(connection, requirement_id):
    return [dict(item) for item in connection.execute('SELECT h.id,h.actor_id,h.action,h.created_at,u.name AS actor_name FROM requirement_history h LEFT JOIN users u ON u.id=h.actor_id WHERE h.requirement_id=? ORDER BY h.id DESC LIMIT 100', (requirement_id,))]


def _get_requirement_detail(connection, requirement_id, include_history=True, report_rows=None):
    row = (report_rows['requirement'] if report_rows is not None else connection.execute('SELECT r.*, u.name AS assigned_reviewer FROM requirements r LEFT JOIN users u ON u.id=r.assigned_reviewer_user_id WHERE r.id = ?', (requirement_id,)).fetchone())
    if row is None:
        return None
    requirement = dict(row)
    from services.integrated_service import review_status
    requirement['sqa_review_status'] = review_status(requirement)
    requirement['review_valid'] = requirement['sqa_review_status']=='Approved'
    requirement['history'] = _get_requirement_history(connection, requirement_id) if include_history else []
    requirement['needs_confirmation'] = bool(requirement['needs_confirmation'])
    try:
        analysis = json.loads(requirement.get('analysis_summary') or '{}')
        requirement['analysis_summary'] = analysis if isinstance(analysis, dict) else {}
    except (ValueError, TypeError):
        requirement['analysis_summary'] = {}
    if requirement.get('reviewed_by_user_id') is not None:
        reviewer = ({'name': report_rows['reviewed_by_name']} if report_rows is not None else connection.execute('SELECT name FROM users WHERE id = ?', (requirement['reviewed_by_user_id'],)).fetchone())
        requirement['reviewed_by_name'] = reviewer['name'] if reviewer else None
    else:
        requirement['reviewed_by_name'] = None
    requirement['acceptance_criteria'] = [dict(item) for item in (report_rows['criteria'] if report_rows is not None else connection.execute('SELECT criterion_code, description, source, needs_confirmation, introduced_values FROM requirement_acceptance_criteria WHERE requirement_id = ? ORDER BY id', (requirement_id,)).fetchall())]
    for criterion in requirement['acceptance_criteria']:
        criterion['needs_confirmation'] = bool(criterion['needs_confirmation'])
        criterion['introduced_values'] = json.loads(criterion['introduced_values'])
        criterion['needs_review'] = bool(row['criteria_review_required'])
    scenarios = ([v for v in report_rows['cases'] if not v['archived']] if report_rows is not None else connection.execute('SELECT * FROM test_scenarios WHERE requirement_id = ? AND archived=0 ORDER BY id', (requirement_id,)).fetchall())
    requirement['test_scenarios'] = []
    for scenario_row in scenarios:
        scenario = dict(scenario_row)
        scenario['criterion_codes'] = json.loads(scenario.get('criterion_codes') or '[]')
        scenario['preconditions'] = json.loads(scenario['preconditions'])
        scenario['test_steps'] = json.loads(scenario['test_steps'])
        scenario['needs_confirmation'] = bool(scenario['needs_confirmation'])
        scenario['introduced_values'] = json.loads(scenario['introduced_values'])
        scenario['assumption_reasons'] = json.loads(scenario['assumption_reasons'])
        requirement['test_scenarios'].append(scenario)
    assumptions = (report_rows['assumptions'] if report_rows is not None else connection.execute('SELECT assumption_code, description, source, needs_confirmation, introduced_values FROM requirement_assumptions WHERE requirement_id = ? ORDER BY id', (requirement_id,)).fetchall())
    requirement['assumptions'] = [dict(item) for item in assumptions]
    for assumption in requirement['assumptions']:
        assumption['needs_confirmation'] = bool(assumption['needs_confirmation'])
        assumption['introduced_values'] = json.loads(assumption['introduced_values'])
    codes = {item['criterion_code'] for item in requirement['acceptance_criteria']}
    linked = {code for item in requirement['test_scenarios'] if item['requirement_revision'] == row['content_revision'] for code in item['criterion_codes']}
    requirement['coverage_gaps'] = sorted(codes - linked)
    requirement['invalid_criterion_links'] = sorted(linked - codes)
    requirement['unlinked_scenarios'] = [item['scenario_code'] for item in requirement['test_scenarios'] if not item['criterion_codes']]
    # Read saved proposals only. Viewing a page never invokes the provider.
    from services.project_service import current_project
    from services.analysis_receipts import bound_input, input_hash
    project = report_rows['project'] if report_rows is not None else current_project(connection)
    requirement['project'] = project
    requirement['analysis_draft'] = None
    if report_rows is None and has_request_context() and getattr(g, 'current_user', None) is not None:
        inputs = bound_input(connection, dict(title=row['title'], description=row['description'], requirement_type=row['requirement_type'], priority=row['user_priority'], clarifications=requirement['analysis_summary'].get('clarifications', '')), row, project)
        draft = connection.execute('SELECT result FROM requirement_analysis_drafts WHERE requirement_id=? AND requirement_revision=? AND user_id=? AND input_hash=?',
                                   (requirement_id, row['revision'], g.current_user['id'], input_hash(inputs))).fetchone()
        if draft:
            requirement['analysis_draft'] = json.loads(draft['result'])
    saved_input = requirement['analysis_summary'].get('analysis_input')
    from analyzers.llm_analyzer import generation_configuration
    requirement['analysis_outdated'] = bool(requirement['analysis_summary'].get('stale') or saved_input and (saved_input.get('context_revision') != project['revision'] or saved_input.get('generation_config') != generation_configuration()))
    return requirement

def _project_report_summary(connection, integrated=None):
    from services.integrated_service import metrics
    integrated=metrics(connection) if integrated is None else integrated
    rows = connection.execute("SELECT review_status, risk_level, requirement_type, risk_score FROM requirements WHERE project_id='current'").fetchall()
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
    traceable_requirement_count = integrated['requirements_with_all_criteria_linked']
    review_counts = integrated['review_status_counts']
    total_test_scenarios = integrated['current_test_case_count']
    high_attention_requirements = [dict(row) for row in connection.execute("SELECT id, title, risk_score, risk_level, review_status FROM requirements WHERE project_id='current' AND (risk_level IN ('High', 'Critical') OR review_status = 'Needs Revision') ORDER BY CASE risk_level WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 ELSE 2 END, risk_score DESC, COALESCE(updated_at, created_at) DESC, id DESC").fetchall()]
    return {'total_requirements': total_requirements, 'review_counts': review_counts, 'risk_counts': risk_counts, 'type_counts': type_counts, 'average_risk_score': round(sum(risk_scores) / len(risk_scores), 1) if risk_scores else None, 'total_test_scenarios': total_test_scenarios, 'traceable_requirement_count': traceable_requirement_count, 'traceability_coverage_percent': round(traceable_requirement_count * 100 / total_requirements, 1) if total_requirements else 0, 'high_attention_requirements': high_attention_requirements}

def _download_response(file_stream, filename, mimetype):
    response = send_file(file_stream, mimetype=mimetype, as_attachment=True, download_name=filename, max_age=0)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

def _save_review(requirement_id, data, required_fields=()):
    from flask import abort
    from services.workflow_service import locked_requirement, snapshot
    if not isinstance(data, dict) or any(f not in data for f in required_fields) or not any(f in data for f in ('review_status','reviewer_notes')):
        abort(400, description='Include the required review fields.')
    if g.current_user['role'] != 'SQA Engineer':
        abort(403, description='Only SQE Engineers may review requirements.')
    c = get_connection()
    try:
        with c:
            row = locked_requirement(c, requirement_id, data)
            if row['created_by_user_id'] == g.current_user['id']:
                abort(403, description='Authors cannot approve or review their own requirements.')
            target = data.get('review_status', row['review_status'])
            if not isinstance(target, str) or target not in REVIEW_STATUSES:
                abort(400, description='Choose a valid review status.')
            allowed = {'Pending': {'In Review'}, 'Ready for Review': {'In Review'},
                       'In Review': {'In Review', 'Approved', 'Needs Revision'}}
            if row['review_status']=='Approved' and row['reviewed_content_revision']!=row['content_revision']:
                allowed['Approved']={'In Review'}  # Re-review legacy approval of unknown source version.
            if target not in allowed.get(row['review_status'], set()):
                abort(409, description='Start a submitted review before deciding; revisions must be resubmitted by an Analyst.')
            notes = data.get('reviewer_notes', row['reviewer_notes'])
            if not isinstance(notes, str) or len(notes)>20000:
                abort(400, description='Reviewer notes must be text of at most 20,000 characters.')
            if target == 'Needs Revision' and not notes.strip():
                abort(400, description='Explain the requested changes.')
            snapshot(c, requirement_id, 'before_review_transition')
            now = _utc_timestamp()
            c.execute('UPDATE requirements SET review_status=?,reviewer_notes=?,reviewed_by_user_id=?,reviewed_at=?,updated_at=?,reviewed_content_revision=?,criteria_review_required=?,revision=revision+1 WHERE id=?',
                      (target,notes.strip(),g.current_user['id'],now,now,row['content_revision'],0 if target=='Approved' else row['criteria_review_required'],requirement_id))
            evidence = {
                'requirement_revision':row['revision'],
                'case_version_ids':[v[0] for v in c.execute('SELECT v.id FROM test_case_versions v JOIN test_scenarios s ON s.id=v.scenario_id WHERE s.requirement_id=? AND v.requirement_revision=?',(requirement_id,row['content_revision']))],
                'execution_ids':[v[0] for v in c.execute('SELECT e.id FROM test_executions e JOIN test_scenarios s ON s.id=e.scenario_id WHERE s.requirement_id=? AND e.requirement_revision=?',(requirement_id,row['content_revision']))],
                'bug_ids':[v[0] for v in c.execute('SELECT id FROM bugs WHERE requirement_id=?',(requirement_id,))],
            }
            c.execute("INSERT INTO requirement_reviews(requirement_id,project_id,content_revision,status,reviewer_id,reviewer_name,notes,reviewed_at,snapshot) VALUES(?,'current',?,?,?,?,?,?,?)",
                      (requirement_id,row['content_revision'],target,g.current_user['id'],g.current_user['name'],notes.strip(),now,json.dumps(evidence)))
            # Approval never silently confirms AI assumptions or business decisions.
            snapshot(c, requirement_id, 'review_'+target.lower().replace(' ','_'))
            return response_payload(requirement=_get_requirement_detail(c,requirement_id))
    finally:
        c.close()
