"""One bounded live provider call with disposable SQLite and synthetic inputs."""
import json
import logging
import time
from pathlib import Path
import app
from test_admin_dashboard import ManagerTests, HEADERS

logging.disable(logging.CRITICAL)
ManagerTests.setUpClass()
fixture = ManagerTests()
fixture.setUp()
try:
    client = fixture.client(2)
    payload = dict(title='Synthetic shipment latency', description='Under 200 simultaneous authenticated users, 95% of shipment-status API responses must complete within 2 seconds during a 30-minute load test.', requirement_type='Non-Functional', priority='Medium')
    start = time.perf_counter()
    response = client.post('/api/analyze-requirement', json=payload, headers=HEADERS)
    evidence = dict(environment='local Flask test client, temporary SQLite, live configured Gemini', analysis_ms=round((time.perf_counter()-start)*1000, 2), analysis_http=response.status_code, analysis=response.json)
    if response.status_code == 200:
        saved = client.post('/api/requirements', json={**payload, 'analysis':response.json}, headers={**HEADERS, 'Idempotency-Key':'live-synthetic-journey'})
        assert saved.status_code == 201, saved.json
        rid = saved.json['requirement']['id']
        reopened = client.get(f'/api/requirements/{rid}').json['requirement']
        assert reopened['analysis_summary']['analysis_version'] == 3
        assert reopened['risk_score'] is None
        assert all(v['needs_confirmation'] for v in reopened['acceptance_criteria']+reopened['test_scenarios'])
        assert not reopened['coverage_gaps']
        pdf = client.get(f'/api/requirements/{rid}/report.pdf')
        assert pdf.status_code == 200 and pdf.data.startswith(b'%PDF-')
        evidence.update(save_http=saved.status_code, reopen='passed', stored_rows=len(fixture.sql('SELECT id FROM requirements')), linked_scenarios=len(reopened['test_scenarios']), report_bytes=len(pdf.data))
    Path('audit/reliability-followup/live-api-journey.json').write_text(json.dumps(evidence,indent=2), encoding='utf-8')
    print(json.dumps({key:value for key,value in evidence.items() if key!='analysis'}))
    assert response.status_code == 200, 'Live analysis unavailable; see sanitized evidence.'
finally:
    fixture.tearDown()
