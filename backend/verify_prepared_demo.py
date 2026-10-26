"""Verify the prepared local demo with generated credentials; never log secrets."""
import argparse
from contextlib import nullcontext
from io import BytesIO
import json
import logging
from pathlib import Path
import re
from time import perf_counter
from unittest.mock import patch
from prepare_demo import DEFAULT_DIRECTORY, configure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Opt in to one real AI request using synthetic demo text.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    configure(DEFAULT_DIRECTORY)
    import app
    from pypdf import PdfReader
    from test_ai_workflow import valid_analysis
    logging.disable(logging.CRITICAL)
    credentials = dict(re.findall(r'Email: ([^\n]+)\nPassword: ([^\n]+)', (DEFAULT_DIRECTORY / 'credentials.txt').read_text()))
    evidence = dict(database='isolated prepared local demo', ai='LIVE' if args.live else 'MOCKED', timings_ms={})

    def client(label):
        c = app.app.test_client()
        start = perf_counter()
        r = c.post('/api/auth/login', json=dict(email=label+'@demo.invalid', password=credentials[label+'@demo.invalid']), base_url='https://localhost')
        assert r.status_code == 200, ('login', label, r.status_code)
        evidence['timings_ms']['login_'+label] = round((perf_counter()-start)*1000, 2)
        return c, {'X-CSRF-Token': r.json['csrf_token']}

    analyst, a_headers = client('analyst')
    engineer, e_headers = client('engineer')
    admin, _ = client('admin')
    def write(c, method, path, data, headers):
        r = getattr(c, method)(path, json=data, headers=headers, base_url='https://localhost')
        assert r.status_code in (200,201), (method, path, r.status_code)
        return r.json

    body = dict(title='[DEMO] Verified owned-ticket access', description='An authenticated customer can view the subject and description of a support ticket they own. Requests for another customer ticket return access denied without ticket content.', requirement_type='Functional', priority='High')
    r = write(analyst, 'post', '/api/requirements', body, {**a_headers, 'Idempotency-Key':'prepared-demo-workflow-v1'})['requirement']
    provider = nullcontext() if args.live else patch('analyzers.ai_analyzer.analyze_with_llm', return_value=dict(status='success',analysis=valid_analysis()))
    with provider:
        start = perf_counter()
        analysis = write(analyst, 'post', '/api/analyze-requirement', {**body, 'requirement_id':r['id'], 'requirement_revision':r['revision']}, a_headers)
        evidence['timings_ms']['analysis'] = round((perf_counter()-start)*1000,2)
    r = write(analyst,'patch',f'/api/requirements/{r["id"]}/analysis', dict(revision=r['revision'], title=r['title'], description=r['description'],analysis=analysis),a_headers)['requirement']
    assert r['acceptance_criteria'] and r['test_scenarios'] and r['risk_level']
    r = write(analyst,'post',f'/api/requirements/{r["id"]}/submit',dict(revision=r['revision']),a_headers)['requirement']
    for status in ('In Review','Approved'):
        r = write(engineer,'patch',f'/api/requirements/{r["id"]}/review',dict(revision=r['revision'],review_status=status,reviewer_notes='[DEMO] Synthetic SQA review of this saved source version; AI suggestions still require stakeholder confirmation.'),e_headers)['requirement']
    path = f'/api/requirements/{r["id"]}'
    reopened = analyst.get(path,base_url='https://localhost').json['requirement']
    assert reopened['description']==body['description'] and reopened['review_status']=='Approved'
    trace = engineer.get(path+'/traceability',base_url='https://localhost')
    assert trace.status_code==200 and trace.json['reviews']
    denied = analyst.patch(path+'/review',json=dict(revision=r['revision'],review_status='In Review'),headers=a_headers,base_url='https://localhost')
    assert denied.status_code==403
    start = perf_counter()
    pdf = engineer.get(path+'/report.pdf',base_url='https://localhost')
    evidence['timings_ms']['pdf'] = round((perf_counter()-start)*1000,2)
    assert pdf.status_code==200 and pdf.mimetype=='application/pdf'
    reader = PdfReader(BytesIO(pdf.data))
    assert all(page.extract_text() and len(page.images) for page in reader.pages)
    assert '[DEMO] Verified owned-ticket access' in ''.join(page.extract_text() for page in reader.pages)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.with_suffix('.pdf').write_bytes(pdf.data)
    dashboard = admin.get('/api/admin/dashboard',base_url='https://localhost')
    assert dashboard.status_code==200 and dashboard.json['summary']['total'] >= 5
    evidence.update(requirement_id=r['id'],saved_after_reopen=True,criteria=len(r['acceptance_criteria']),scenarios=len(r['test_scenarios']),risk=r['risk_level'],review='Approved synthetic local review',traceability='passed',analyst_review_denied=403,pdf_pages=len(reader.pages),pdf_bytes=len(pdf.data),dashboard_total=dashboard.json['summary']['total'])
    args.output.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence))


if __name__=='__main__':
    main()
