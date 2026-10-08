import json,time,tempfile
from pathlib import Path
from unittest.mock import patch
import app
from werkzeug.security import generate_password_hash
from statistics import median
password='benchmark-only-password'
with tempfile.TemporaryDirectory() as folder, patch.multiple(app,DATABASE_URL=None,DATABASE=Path(folder)/'benchmark.db'):
 c=app.get_connection()
 for role in ('admin','Analyst'):
  c.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',(role,role.lower()+'@example.com',generate_password_hash(password,method='scrypt'),role))
 c.commit();c.close()
 client=app.app.test_client()
 for role in ('admin','Analyst'):
  timings=[]; counts=[]
  for _ in range(3):
   from services import auth_service,requirement_helpers
   opens=[0]
   def connect():
    opens[0]+=1
    return app.get_connection()
   with patch.object(auth_service,'get_connection',side_effect=connect),patch.object(requirement_helpers,'get_connection',side_effect=connect):
    t=time.perf_counter();response=client.post('/api/auth/login',base_url='https://localhost',json={'email':role.lower()+'@example.com','password':password});timings.append(round((time.perf_counter()-t)*1000,2));counts.append(opens[0]);assert response.status_code==200
  print(json.dumps({'role':role,'milliseconds':timings,'median_ms':median(timings),'connections':counts}))
