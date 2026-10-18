"""Comparable endpoint timings with temporary SQLite and synthetic data only."""
import json, logging, time, math
from database import DatabaseConnection
from statistics import median
from unittest.mock import patch
import app
from test_admin_dashboard import ManagerTests, HEADERS, PASSWORD
logging.disable(logging.CRITICAL)
ManagerTests.setUpClass();f=ManagerTests();f.setUp()
try:
    for i in range(100):
        rid=f.requirement(title=f'Requirement {i}',analysis_summary=json.dumps({'improved_requirement':'Synthetic refinement. '*200}))
        f.criteria(rid);f.scenario(rid)
    analyst=f.client(2)
    payload=dict(title='Synthetic sign in',description='Registered users can sign in with valid credentials.',requirement_type='Functional',priority='Medium')
    cases=[('login','post','/api/auth/login',{'email':'analyst@example.com','password':PASSWORD}),
           ('session','get','/api/auth/me',None),('dashboard','get','/api/dashboard',None),
           ('list_summary','get','/api/requirements?view=summary',None),
           ('details','get',f'/api/requirements/{rid}',None),('save','post','/api/requirements',payload),
           ('requirement_report','get',f'/api/requirements/{rid}/report.pdf',None),
           ('project_report','get','/api/reports/project.pdf',None),('csv','get','/api/exports/requirements.csv',None)]
    original_execute=DatabaseConnection.execute
    query_count=[0]
    def measured_execute(c,statement,parameters=()):
        if c._instrument:query_count[0]+=1
        return original_execute(c,statement,parameters)
    DatabaseConnection.execute=measured_execute
    for name,method,url,data in cases:
        samples=[];query_counts=[]
        client=app.app.test_client() if name=='login' else analyst
        for sample in range(21):
            if name=='login':f.sql('DELETE FROM request_limits')
            query_count[0]=0
            start=time.perf_counter()
            response=getattr(client,method)(url,base_url='https://localhost',**({'json':data,'headers':{**HEADERS,**({'Idempotency-Key':f'benchmark-save-{sample}'} if name=='save' else {})}} if data else {}))
            samples.append(round((time.perf_counter()-start)*1000,2));query_counts.append(query_count[0])
            assert response.status_code in (200,201),(name,response.status_code,response.json)
        print(json.dumps(dict(operation=name,first_request_ms=samples[0],warm_median_ms=median(samples[1:]),warm_samples_ms=samples[1:],warm_p95_ms=sorted(samples[1:])[math.ceil(.95*20)-1],warm_n=20,queries_median=median(query_counts[1:]),http_requests_per_action=1,bytes=len(response.data),server_timing=response.headers.get('Server-Timing'))),flush=True)
finally: f.tearDown()
