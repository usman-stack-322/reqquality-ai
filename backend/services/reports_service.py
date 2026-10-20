import csv
from io import BytesIO, StringIO
from app import get_connection
from services.requirement_helpers import _get_requirement_detail, _project_report_summary, _download_response
from services.responses import response_payload

def export_requirement_pdf(requirement_id):
    from reporting import build_requirement_pdf
    connection = get_connection()
    try:
        requirement = _get_requirement_detail(connection, requirement_id)
        if requirement:
            from services.integrated_service import graph
            requirement['integrated']=graph(connection,requirement_id)
    finally:
        connection.close()
    if requirement is None:
        return (response_payload(error='Requirement not found.'), 404)
    return _download_response(build_requirement_pdf(requirement), f'reqquality-requirement-{requirement_id}.pdf', 'application/pdf')

def export_project_pdf():
    from reporting import build_project_summary_pdf
    connection = get_connection()
    try:
        summary = _project_report_summary(connection)
        from services.integrated_service import metrics,graph
        summary['integrated']=metrics(connection)
        summary['requirements']=[dict(_get_requirement_detail(connection,v[0]),integrated=graph(connection,v[0])) for v in connection.execute("SELECT id FROM requirements WHERE project_id='current' ORDER BY id")]
    finally:
        connection.close()
    return _download_response(build_project_summary_pdf(summary), 'reqquality-project-summary.pdf', 'application/pdf')

def export_requirements_csv():
    import json
    fields = ('id', 'title', 'requirement_type', 'user_priority', 'suggested_priority', 'risk_score', 'risk_level', 'review_status', 'created_at', 'updated_at', 'project_id', 'content_revision', 'sqa_review_status', 'reviewed_content_revision', 'reviewed_by_name', 'reviewer_notes', 'reviewed_at', 'description', 'analysis_outdated', 'criteria_review_required', 'acceptance_criteria', 'requirement_versions', 'test_cases', 'case_versions', 'executions', 'bugs', 'bug_history', 'reviews', 'metric_definitions')
    connection = get_connection()
    try:
        from services.integrated_service import graph
        rows=[]
        for item in connection.execute("SELECT id FROM requirements WHERE project_id='current' ORDER BY id").fetchall():
            r=_get_requirement_detail(connection,item[0]); linked=graph(connection,item[0])
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
