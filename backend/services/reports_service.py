import csv
from io import BytesIO, StringIO
from reporting import build_project_summary_pdf, build_requirement_pdf
from app import get_connection
from services.requirement_helpers import _get_requirement_detail, _project_report_summary, _download_response
from services.responses import response_payload

def export_requirement_pdf(requirement_id):
    connection = get_connection()
    try:
        requirement = _get_requirement_detail(connection, requirement_id)
    finally:
        connection.close()
    if requirement is None:
        return (response_payload(error='Requirement not found.'), 404)
    return _download_response(build_requirement_pdf(requirement), f'reqquality-requirement-{requirement_id}.pdf', 'application/pdf')

def export_project_pdf():
    connection = get_connection()
    try:
        summary = _project_report_summary(connection)
    finally:
        connection.close()
    return _download_response(build_project_summary_pdf(summary), 'reqquality-project-summary.pdf', 'application/pdf')

def export_requirements_csv():
    fields = ('id', 'title', 'requirement_type', 'user_priority', 'suggested_priority', 'risk_score', 'risk_level', 'review_status', 'created_at', 'updated_at')
    connection = get_connection()
    try:
        rows = connection.execute('SELECT id, title, requirement_type, COALESCE(user_priority, priority) AS user_priority, suggested_priority, risk_score, risk_level, review_status, created_at, updated_at FROM requirements ORDER BY id').fetchall()
    finally:
        connection.close()
    output = StringIO(newline='')
    writer = csv.writer(output, lineterminator='\r\n')
    writer.writerow(fields)
    for row in rows:
        cells = []
        for field in fields:
            value = row[field]
            if isinstance(value, str) and value.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')):
                value = "'" + value
            cells.append(value)
        writer.writerow(cells)
    return _download_response(BytesIO(output.getvalue().encode('utf-8-sig')), 'reqquality-requirements.csv', 'text/csv; charset=utf-8')
