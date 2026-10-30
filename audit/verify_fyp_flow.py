"""Presentation rehearsal against disposable SQLite; --live explicitly uses Gemini.
Never opens the configured production database or prints passwords/provider responses.
"""
import argparse
from contextlib import ExitStack
import csv
from io import BytesIO,StringIO
import json
import logging
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
parser=argparse.ArgumentParser()
parser.add_argument('--live',action='store_true')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
import app
from flask import g
from pypdf import PdfReader
from test_admin_dashboard import ManagerTests,PASSWORD
from test_ai_workflow import valid_analysis
from analyzers.review_assistant import FIELDS
logging.disable(logging.CRITICAL)
ManagerTests.setUpClass();fixture=ManagerTests();fixture.setUp()
evidence={'database':'disposable SQLite','AI':'live Gemini' if args.live else 'mocked Gemini','login':[],'exports':[],'checks':[]}
def record(name):evidence['checks'].append(name)
def write(client,method,path,body,csrf):
    response=getattr(client,method)(path,json=body,headers={'X-CSRF-Token':csrf})
    assert response.status_code in (200,201),(path,response.status_code)
    return response.json
try:
    analyst=app.app.test_client();engineer=app.app.test_client()
    for label,client,email in [('Analyst',analyst,'analyst@example.com'),('SQA Engineer',engineer,'engineer@example.com')]:
        started=perf_counter()
        with client:
            response=client.post('/api/auth/login',json={'email':email,'password':PASSWORD})
            assert response.status_code==200
            evidence['login'].append(dict(role=label,http_status=200,attempts=1,elapsed_ms=round((perf_counter()-started)*1000,2),stages_ms={k:round(v,2) for k,v in g.login_timings.items()}))
        if label=='Analyst':a=response.json['csrf_token']
        else:e=response.json['csrf_token']
    record('Both roles sign in on first valid submission')
    body=dict(title='[FYP DEMO] Valid sign-in',description='A registered active user signs in with their valid email and password. Successful sign-in opens the user dashboard. Both fields are required; empty email or password is rejected without opening the dashboard.',requirement_type='Functional',priority='High')
    r=write(analyst,'post','/api/requirements',body,a)['requirement'];rid=r['id'];path=f'/api/requirements/{rid}'
    record('Requirement created by Analyst')
    with ExitStack() as stack:
        if not args.live:stack.enter_context(patch('analyzers.ai_analyzer.analyze_with_llm',return_value={'status':'success','analysis':valid_analysis()}))
        started=perf_counter()
        analysis=write(analyst,'post','/api/analyze-requirement',{**body,'requirement_id':rid,'requirement_revision':r['revision']},a)
        evidence['analysis_ms']=round((perf_counter()-started)*1000,2)
    r=write(analyst,'patch',path+'/analysis',{'revision':r['revision'],'title':r['title'],'description':r['description'],'analysis':analysis},a)['requirement']
    assert r['description']==body['description'] and r['acceptance_criteria'] and r['test_scenarios']
    record('AI analysis accepted explicitly; original requirement preserved')
    cases=engineer.get(path+'/test-cases').json['test_cases'];case=cases[0]
    session=write(engineer,'post',path+'/ai-review',{'case_ids':[case['id']]},e)
    content={k:case[k] for k in FIELDS};content['title']='Verify valid sign-in'
    proposal={'kind':'proposal','message':'Updated the selected title only.','changes':[{'operation':'revise','case_id':case['id'],'summary':'Use an action-oriented title.','content':content}]}
    with ExitStack() as stack:
        if not args.live:stack.enter_context(patch('analyzers.review_assistant.generate_review',return_value=proposal))
        generated=write(engineer,'post',path+f"/ai-review/{session['id']}/messages",{'feedback':"Revise only the selected case title to 'Verify valid sign-in'. Preserve all other checks and content. Do not add cases or behavior.",'request_key':'fyp-title-revision'},e)['turn']
    assert generated['proposal']['kind']=='proposal'
    assert engineer.get(path+'/test-cases').json['test_cases'][0]['case_revision']==case['case_revision']
    r=write(engineer,'post',path+f"/ai-review/{session['id']}/proposals/{generated['id']}",{'action':'accept'},e)['requirement']
    record('AI Review Assistant proposal leaves saved cases unchanged until acceptance')
    cases=engineer.get(path+'/test-cases').json['test_cases']
    revised=next(c for c in cases if c['id']==case['id']);assert revised['review_status']=='Pending Review'
    for c in cases:
        for status in ('In Review','Approved'):
            r=write(engineer,'patch',path+f"/test-cases/{c['id']}/review",{'revision':r['revision'],'case_revision':c['case_revision'],'review_status':status,'review_notes':'Synthetic FYP rehearsal: source and expected behavior reviewed.'},e)['requirement']
            c=next(x for x in engineer.get(path+'/test-cases').json['test_cases'] if x['id']==c['id'])
    record('Accepted case Pending Review; separately reviewed and approved by SQA')
    r=write(analyst,'post',path+'/submit',{'revision':r['revision']},a)['requirement']
    for status in ('In Review','Approved'):
        r=write(engineer,'patch',path+'/review',{'revision':r['revision'],'review_status':status,'reviewer_notes':'Synthetic local rehearsal review, not supervisor or production approval.'},e)['requirement']
    record('Requirement submitted by Analyst and approved by separate SQA actor')
    assert analyst.patch(path+'/review',json={'revision':r['revision'],'review_status':'Approved'},headers={'X-CSRF-Token':a}).status_code==403
    record('Analyst approval forbidden')
    for sample in range(3):
        for name,url in [('requirement',path+'/report.pdf'),('project','/api/reports/project.pdf'),('requirements','/api/exports/requirements.csv')]:
            started=perf_counter();response=engineer.get(url);duration=round((perf_counter()-started)*1000,2)
            assert response.status_code==200
            kind='csv' if name=='requirements' else 'pdf'
            (args.output/f'{name}.{kind}').write_bytes(response.data)
            if kind=='pdf':
                reader=PdfReader(BytesIO(response.data));text='\n'.join(p.extract_text() or '' for p in reader.pages)
                assert '[FYP DEMO] Valid sign-in' in text and 'Approved' in text
            else:
                rows=list(csv.DictReader(StringIO(response.data.decode('utf-8-sig'))))
                assert rows[0]['title']==body['title'] and rows[0]['review_status']=='Approved'
                assert 'Verify valid sign-in' in rows[0]['test_cases']
            evidence['exports'].append(dict(name=name,sample=sample+1,elapsed_ms=duration,bytes=len(response.data),server_timing=response.headers.get('Server-Timing','')))
    record('PDFs reopened with pypdf; CSV parsed with source, approval and revised case')
    trace=engineer.get(path+'/traceability').json
    assert trace['case_versions'] and trace['reviews']
    record('Version and approval traceability preserved')
    evidence['status']='passed'
except Exception as error:
    evidence.update(status='blocked',error_type=type(error).__name__)
    raise
finally:
    (args.output/'result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    fixture.tearDown()
print(json.dumps(evidence))
