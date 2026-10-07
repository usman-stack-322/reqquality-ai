from app import get_connection
from services.responses import response_payload

def dashboard_summary():
    connection = get_connection()
    try:
        totals = connection.execute("SELECT COUNT(*) AS total_requirements, SUM(CASE WHEN review_status = 'Pending' THEN 1 ELSE 0 END) AS pending_count, SUM(CASE WHEN review_status = 'In Review' THEN 1 ELSE 0 END) AS in_review_count, SUM(CASE WHEN review_status = 'Approved' THEN 1 ELSE 0 END) AS approved_count, SUM(CASE WHEN review_status = 'Needs Revision' THEN 1 ELSE 0 END) AS needs_revision_count, SUM(CASE WHEN risk_level = 'Low' THEN 1 ELSE 0 END) AS low_risk_count, SUM(CASE WHEN risk_level = 'Medium' THEN 1 ELSE 0 END) AS medium_risk_count, SUM(CASE WHEN risk_level = 'High' THEN 1 ELSE 0 END) AS high_risk_count, SUM(CASE WHEN risk_level = 'Critical' THEN 1 ELSE 0 END) AS critical_risk_count, SUM(CASE WHEN requirement_type = 'Functional' THEN 1 ELSE 0 END) AS functional_count, SUM(CASE WHEN requirement_type = 'Non-Functional' THEN 1 ELSE 0 END) AS non_functional_count, SUM(CASE WHEN requirement_type = 'Business' THEN 1 ELSE 0 END) AS business_count, COALESCE(ROUND(AVG(risk_score), 1), 0) AS average_risk_score FROM requirements").fetchone()
        total_scenarios = connection.execute('SELECT COUNT(*) FROM test_scenarios').fetchone()[0]
        traceable_count = connection.execute('SELECT COUNT(*) FROM requirements AS requirement WHERE EXISTS (SELECT 1 FROM requirement_acceptance_criteria AS criterion WHERE criterion.requirement_id = requirement.id) AND EXISTS (SELECT 1 FROM test_scenarios AS scenario WHERE scenario.requirement_id = requirement.id)').fetchone()[0]
        requirement_fields = 'id, title, description, requirement_type, priority, user_priority, suggested_priority, risk_score, risk_level, review_status, created_at, updated_at'
        recent_requirements = connection.execute(f'SELECT {requirement_fields} FROM requirements ORDER BY COALESCE(updated_at, created_at) DESC, id DESC LIMIT 5').fetchall()
        high_attention_requirements = connection.execute(f"SELECT {requirement_fields} FROM requirements WHERE risk_level IN ('High', 'Critical') OR review_status = 'Needs Revision' ORDER BY CASE risk_level WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 ELSE 2 END, risk_score DESC, COALESCE(updated_at, created_at) DESC, id DESC").fetchall()
    finally:
        connection.close()
    total_requirements = int(totals['total_requirements'] or 0)
    status_counts = {field: int(totals[field] or 0) for field in ('pending_count', 'in_review_count', 'approved_count', 'needs_revision_count')}
    risk_counts = {field: int(totals[field] or 0) for field in ('low_risk_count', 'medium_risk_count', 'high_risk_count', 'critical_risk_count')}
    type_counts = {field: int(totals[field] or 0) for field in ('functional_count', 'non_functional_count', 'business_count')}
    average_risk_score = float(totals['average_risk_score'] or 0)
    total_test_scenarios = int(total_scenarios or 0)
    traceable_count = int(traceable_count or 0)
    traceability_coverage = float(round(traceable_count * 100 / total_requirements, 1)) if total_requirements else 0.0
    return response_payload(total_requirements=total_requirements, **status_counts, **risk_counts, **type_counts, average_risk_score=average_risk_score, total_test_scenarios=total_scenarios, traceability_coverage_percent=traceability_coverage, traceable_requirement_count=traceable_count, recent_requirements=[dict(row) for row in recent_requirements], high_attention_requirements=[dict(row) for row in high_attention_requirements])
