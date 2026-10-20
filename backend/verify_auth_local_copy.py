"""Verify saved workstation credentials on an isolated DB backup, never the source."""
import json,logging,sqlite3,tempfile,time
from pathlib import Path
from unittest.mock import patch
import app
from flask import g
logging.disable(logging.CRITICAL)
root=Path(__file__).resolve().parents[1]
values=dict(line.split(': ',1) for line in (root/'backend/instance/local-login.txt').read_text().splitlines() if ': ' in line)
with tempfile.TemporaryDirectory() as directory:
 destination=Path(directory)/'local-copy.db'
 source=sqlite3.connect((root/'backend/instance/local-development.db').resolve().as_uri()+'?mode=ro',uri=True)
 target=sqlite3.connect(destination)
 source.backup(target);target.close();source.close()
 with patch.multiple(app,DATABASE_URL=None,DATABASE=destination):
  client=app.app.test_client()
  for sample in range(3):
   with client:
    start=time.perf_counter()
    response=client.post('/api/auth/login',base_url='https://localhost',json={'email':values['Email'],'password':values['Password']})
    assert response.status_code==200
    print(json.dumps({'sample':sample+1,'valid_login':response.status_code,'request_ms':round((time.perf_counter()-start)*1000,2),'stages_ms':{k:round(v,2) for k,v in g.login_timings.items()}}))
   csrf=response.json['csrf_token']
   assert client.get('/api/auth/me',base_url='https://localhost').json['authenticated']
   assert client.get('/api/admin/dashboard',base_url='https://localhost').status_code==200
   assert client.post('/api/requirements',base_url='https://localhost',json={},headers={'X-CSRF-Token':csrf}).status_code==403
   assert client.post('/api/auth/logout',base_url='https://localhost',headers={'X-CSRF-Token':csrf}).status_code==200
   assert not client.get('/api/auth/me',base_url='https://localhost').json['authenticated']
  invalid=client.post('/api/auth/login',base_url='https://localhost',json={'email':values['Email'],'password':'deliberately-incorrect-fixture'})
  assert invalid.status_code==401
  print(json.dumps({'session_persistence':'passed','role_restriction':'passed','logout':'passed','invalid_login':invalid.status_code,'source_database':'read-only backup; untouched'}))
