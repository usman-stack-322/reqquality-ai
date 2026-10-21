"""Sequential isolated V1 request timings; no live DB, no provider calls or rate-limit bypass."""
import argparse
import json
import logging
import math
import os
import platform
import sqlite3
import statistics
import time
from importlib.metadata import version
from pathlib import Path
from contextlib import nullcontext
from unittest.mock import patch
import app
from flask import g
from test_integrated_reporting import IntegratedReportingTests
from test_admin_dashboard import PASSWORD

def summary(values):
    ordered=sorted(values)
    return dict(n=len(values),median_ms=round(statistics.median(values),2),p95_ms=round(ordered[math.ceil(.95*len(ordered))-1],2),first_ms=round(values[0],2))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--without-metric-reuse',action='store_true');parser.add_argument('--workflow-dashboard',action='store_true');args=parser.parse_args()
    logging.disable(logging.CRITICAL)
    IntegratedReportingTests.setUpClass();f=IntegratedReportingTests();f.setUp()
    try:
        # Same 100 requirements / 199 cases in each fresh before/after fixture.
        c=app.get_connection()
        with c:
            for index in range(99):
                cursor=c.execute("INSERT INTO requirements(title,description,requirement_type,priority,created_by_user_id,review_status) VALUES(?,?,'Functional','Medium',2,'Pending')",(f'Benchmark requirement {index}','Customers can view their own ticket subjects.'))
                rid=cursor.lastrowid
                c.execute("INSERT INTO requirement_acceptance_criteria(requirement_id,criterion_code,description) VALUES(?,'AC-001','The owner can view the ticket.')",(rid,))
                for category in ('Positive','Negative'):
                    c.execute("INSERT INTO test_scenarios(requirement_id,scenario_code,category,title,preconditions,test_steps,expected_result,criterion_codes,requirement_revision,priority) VALUES(?,?,?,?,'[]',?,'Owner scope is enforced.',?,1,'Medium')",(rid,category,category,'Synthetic owner-scope case',json.dumps(['Request own ticket.','Inspect the response.']),json.dumps(['AC-001'])))
            # 30 distinct synthetic accounts avoid exceeding per-account login limits.
            hash_value=c.execute('SELECT password_hash FROM users WHERE id=2').fetchone()[0]
            for index in range(30):
                c.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'Analyst')",(f'Benchmark {index}',f'bench{index}@example.invalid',hash_value))
        c.close()
        data={};stages={}
        from services import management_service
        original_load=management_service.load_requirements
        for name,client,path in (('dashboard',f.analyst,'/api/dashboard?view=workflow' if args.workflow_dashboard else '/api/dashboard'),('admin_dashboard',f.admin,'/api/admin/dashboard'),('detail',f.analyst,f'/api/requirements/{f.r["id"]}')):
            values=[]
            for _ in range(40):
                # A/B control reproduces the former duplicate read within this
                # one request only. Permissions/security/metric values are unchanged.
                control=(patch.object(management_service,'load_requirements',side_effect=lambda connection,days,metric_data=None:original_load(connection,days)) if args.without_metric_reuse and name=='admin_dashboard' else nullcontext())
                with control:
                    start=time.perf_counter();response=client.get(path);values.append((time.perf_counter()-start)*1000)
                assert response.status_code==200,(name,response.status_code)
            data[name]=summary(values)
        values=[]
        for index in range(30):
            client=app.app.test_client()
            with client:
                start=time.perf_counter();response=client.post('/api/auth/login',base_url='https://localhost',json=dict(email=f'bench{index}@example.invalid',password=PASSWORD));values.append((time.perf_counter()-start)*1000)
                assert response.status_code==200,response.status_code
                for key,value in g.login_timings.items():stages.setdefault(key,[]).append(value)
            assert client.post('/api/auth/logout',base_url='https://localhost',headers={'X-CSRF-Token':response.json['csrf_token']}).status_code==200
        data['login']=summary(values)
        values=[]
        for index in range(30):
            body=dict(title=f.r['title'],description=f'Customers can view only their own ticket subjects. Synthetic revision {index}.',requirement_type='Functional',priority='High',revision=f.r['revision'],acceptance_criteria=[v['description'] for v in f.r['acceptance_criteria']])
            start=time.perf_counter();response=f.write('patch',f'/api/requirements/{f.r["id"]}',body,f.analyst);values.append((time.perf_counter()-start)*1000)
            assert response.status_code==200,response.status_code
            f.r=response.json['requirement']
        data['material_save']=summary(values)
        payload=dict(metric_reuse=not args.without_metric_reuse,environment=dict(os=platform.system(),release=platform.release(),machine=platform.machine(),logical_cpus=os.cpu_count(),python=platform.python_version(),sqlite=sqlite3.sqlite_version,flask=version('Flask')),dataset=dict(requirements=100,test_cases=199,executions=0,bugs=0,synthetic_users=34),transport='Flask test client, sequential single process, temporary local SQLite; initialized schema. Not browser/network/PG or true process-cold timings.',percentile='Nearest rank p95 of 30/40 observations; descriptive sample tail, not production SLA evidence.',requests=data,login_stages_ms={key:summary(values) for key,values in stages.items()})
        payload['workflow_dashboard'] = args.workflow_dashboard
        Path(args.output).write_text(json.dumps(payload,indent=2),encoding='utf-8')
        print(json.dumps(dict(requests=data),sort_keys=True))
    finally:f.doCleanups()

if __name__=='__main__':main()
