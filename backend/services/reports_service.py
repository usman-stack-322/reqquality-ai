import csv
from contextlib import contextmanager
from io import BytesIO, StringIO
from app import get_connection
from services.requirement_helpers import _get_requirement_detail, _project_report_summary, _download_response
from services.responses import response_payload


@contextmanager
def _read_snapshot(connection):
    """Keep one export internally consistent while other users save changes."""
    with connection:
        if connection.dialect == 'postgres':
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        else:
            connection.execute('BEGIN')
        yield


def _report_requirements(connection, requirement_id=None):
    """One request-local snapshot; bounded SELECT count instead of per-record reads.

    Access is checked by the controller before this function. Every query is
    scoped to the shared project; no proposals or cross-user report cache.
    """
    from services.project_service import current_project
    from services.integrated_service import graph
    where = "r.project_id='current'" + (' AND r.id=?' if requirement_id is not None else '')
    parameters = (requirement_id,) if requirement_id is not None else ()
    requirements = connection.execute(
        'SELECT r.*,u.name AS assigned_reviewer,v.name AS reviewed_by_name FROM requirements r '
        'LEFT JOIN users u ON u.id=r.assigned_reviewer_user_id '
        'LEFT JOIN users v ON v.id=r.reviewed_by_user_id WHERE ' + where + ' ORDER BY r.id', parameters).fetchall()
    if not requirements:
        return []
    project = current_project(connection)
    records = {r['id']: dict(requirement=r, reviewed_by_name=r['reviewed_by_name'], project=project,
                            **{key: [] for key in ('criteria', 'assumptions', 'cases', 'versions', 'case_versions', 'executions', 'bugs', 'bug_history', 'reviews')}) for r in requirements}
    queries = {
        'criteria': 'SELECT x.* FROM requirement_acceptance_criteria x JOIN requirements r ON r.id=x.requirement_id',
        'assumptions': 'SELECT x.* FROM requirement_assumptions x JOIN requirements r ON r.id=x.requirement_id',
        'cases': 'SELECT x.* FROM test_scenarios x JOIN requirements r ON r.id=x.requirement_id',
        'versions': 'SELECT x.* FROM requirement_versions x JOIN requirements r ON r.id=x.requirement_id',
        'case_versions': 'SELECT x.*,s.requirement_id AS export_requirement_id FROM test_case_versions x JOIN test_scenarios s ON s.id=x.scenario_id JOIN requirements r ON r.id=s.requirement_id',
        'executions': 'SELECT x.*,s.requirement_id AS export_requirement_id FROM test_executions x JOIN test_scenarios s ON s.id=x.scenario_id JOIN requirements r ON r.id=s.requirement_id',
        'bugs': 'SELECT x.* FROM bugs x JOIN requirements r ON r.id=x.requirement_id',
        'bug_history': 'SELECT x.*,b.requirement_id AS export_requirement_id FROM bug_history x JOIN bugs b ON b.id=x.bug_id JOIN requirements r ON r.id=b.requirement_id',
        'reviews': 'SELECT x.* FROM requirement_reviews x JOIN requirements r ON r.id=x.requirement_id',
    }
    for key, sql in queries.items():
        order = 'x.content_revision DESC' if key == 'versions' else 'x.id'
        for value in connection.execute(sql + ' WHERE ' + where + ' ORDER BY ' + order, parameters):
            row = dict(value)
            rid = row.pop('export_requirement_id', row.get('requirement_id'))
            records[rid][key].append(row)
    result = []
    for rid, rows in records.items():
        detail = _get_requirement_detail(connection, rid, include_history=False, report_rows=rows)
        detail['integrated'] = graph(connection, rid, records=rows)
        result.append(detail)
    return result

def export_requirement_pdf(requirement_id):
    from reporting import build_requirement_pdf
    connection = get_connection()
    try:
        with _read_snapshot(connection):
            rows = _report_requirements(connection, requirement_id)
            requirement = rows[0] if rows else None
    finally:
        connection.close()
    if requirement is None:
        return (response_payload(error='Requirement not found.'), 404)
    return _download_response(build_requirement_pdf(requirement), f'reqquality-requirement-{requirement_id}.pdf', 'application/pdf')

def export_project_pdf():
    from reporting import build_project_summary_pdf
    connection = get_connection()
    try:
        with _read_snapshot(connection):
            from services.integrated_service import metrics
            integrated = metrics(connection)
            summary = _project_report_summary(connection, integrated=integrated)
            summary['integrated'] = integrated
            summary['requirements'] = _report_requirements(connection)
    finally:
        connection.close()
    return _download_response(build_project_summary_pdf(summary), 'reqquality-project-summary.pdf', 'application/pdf')

def export_requirements_csv():
    import json
    fields = ('id', 'title', 'requirement_type', 'user_priority', 'suggested_priority', 'risk_score', 'risk_level', 'review_status', 'created_at', 'updated_at', 'project_id', 'content_revision', 'sqa_review_status', 'reviewed_content_revision', 'reviewed_by_name', 'reviewer_notes', 'reviewed_at', 'description', 'analysis_outdated', 'criteria_review_required', 'acceptance_criteria', 'requirement_versions', 'test_cases', 'case_versions', 'executions', 'bugs', 'bug_history', 'reviews', 'metric_definitions')
    connection = get_connection()
    try:
        with _read_snapshot(connection):
            rows=[]
            for r in _report_requirements(connection):
                linked=r.pop('integrated')
                r.update(requirement_versions=linked['versions'],**{key:linked[key] for key in ('test_cases','case_versions','executions','bugs','bug_history','reviews','metric_definitions')})
                rows.append(r)
    finally:
        connection.close()
    output = StringIO(newline='')
    writer = csv.writer(output, lineterminator='\r\n')
    writer.writerow(fields)
    for row in rows:
        cells = []
        for field in fields:
            value = row[field]
            if isinstance(value,(dict,list)): value=json.dumps(value,ensure_ascii=True)
            if isinstance(value, str) and value.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')):
                value = "'" + value
            cells.append(value)
        writer.writerow(cells)
    return _download_response(BytesIO(output.getvalue().encode('utf-8-sig')), 'reqquality-requirements.csv', 'text/csv; charset=utf-8')
