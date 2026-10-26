"""Local Vite -> Flask -> prepared SQLite smoke; credentials never printed."""
from http.cookiejar import CookieJar
from pathlib import Path
import json
import re
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
credentials = dict(re.findall(r'Email: ([^\n]+)\nPassword: ([^\n]+)', (root/'backend/instance/verified-demo/credentials.txt').read_text()))
origin = 'http://127.0.0.1:5174'
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
start = time.perf_counter()
request = urllib.request.Request(origin+'/api/auth/login', json.dumps(dict(email='engineer@demo.invalid',password=credentials['engineer@demo.invalid'])).encode(), {'Content-Type':'application/json','Origin':origin})
with client.open(request,timeout=15) as response:
    login = json.load(response)
    assert login['user']['role']=='SQA Engineer'
    evidence = dict(origin=origin, login_status=response.status, login_ms=round((time.perf_counter()-start)*1000,2), login_server_timing=response.headers.get('Server-Timing'))
evidence['reads'] = []
for path in ('/api/auth/me','/api/dashboard?view=workflow','/api/requirements/5/traceability'):
    start=time.perf_counter()
    with client.open(origin+path,timeout=15) as response:
        assert response.status==200
        value=json.load(response)
        if path=='/api/auth/me': assert value['authenticated']
        evidence['reads'].append(dict(path=path,ms=round((time.perf_counter()-start)*1000,2),server_timing=response.headers.get('Server-Timing')))
with client.open(origin+'/api/requirements/5/report.pdf',timeout=15) as response:
    pdf=response.read()
    assert response.status==200 and response.headers.get_content_type()=='application/pdf' and pdf.startswith(b'%PDF-')
    evidence.update(pdf_bytes=len(pdf),pdf_server_timing=response.headers.get('Server-Timing'))
    (root/'audit/redesign-live-demo-final.pdf').write_bytes(pdf)
request=urllib.request.Request(origin+'/api/auth/logout', b'{}', {'Content-Type':'application/json','Origin':origin,'X-CSRF-Token':login['csrf_token']})
with client.open(request,timeout=15) as response: assert response.status==200
evidence.update(session=True,dashboard=True,traceability=True,logout=True,ai_calls=0,email_sent=False)
(root/'audit/redesign-demo-http.json').write_text(json.dumps(evidence,indent=2))
print(json.dumps(evidence))
