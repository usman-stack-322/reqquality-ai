"""Comparable auth timings on disposable SQLite; optional read-only configured PG pool."""
import argparse,json,logging,tempfile,time
from pathlib import Path
from unittest.mock import patch
import app
from flask import g
from services import auth_service
from database import connect_database,close_database_pools
from werkzeug.security import generate_password_hash

parser=argparse.ArgumentParser()
parser.add_argument('--postgres',action='store_true')
parser.add_argument('--recovery',action='store_true')
args=parser.parse_args()
logging.disable(logging.CRITICAL)
def emit(**data): print(json.dumps(data),flush=True)
if args.postgres:
    try:
        for sample in range(3):
            start=time.perf_counter()
            c=connect_database(app.DATABASE_URL, 'unused.db')
            acquired=time.perf_counter()
            try:
                with c.autocommit_reads():
                    c.execute('SELECT 1').fetchone()
                queried=time.perf_counter()
            finally: c.close()
            emit(sample=sample+1,connect_ms=round((acquired-start)*1000,2),query_ms=round((queried-acquired)*1000,2),total_ms=round((queried-start)*1000,2))
        if args.recovery:
            # Close only our idle client socket; do not terminate server sessions
            # or touch application records. Verify the next borrower recovers.
            c._connection.close()
            start=time.perf_counter()
            recovered=connect_database(app.DATABASE_URL, 'unused.db')
            try:
                with recovered.autocommit_reads():
                    assert recovered.execute('SELECT 1').fetchone()[0] == 1
                emit(closed_idle_socket_recovery='passed', total_ms=round((time.perf_counter()-start)*1000,2))
            finally: recovered.close()
    except Exception as error:
        from services.database_diagnostics import exception_details
        emit(failure=exception_details(error))
    finally: close_database_pools()
else:
    with tempfile.TemporaryDirectory() as folder,patch.multiple(app,DATABASE_URL=None,DATABASE=Path(folder)/'auth.db'):
        c=app.get_connection()
        with c:
            c.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',('Test admin','admin@example.invalid',generate_password_hash('fixture-only-password',method='scrypt'),'admin'))
        c.close()
        client=app.app.test_client()
        for sample in range(3):
            with client:
                start=time.perf_counter()
                response=client.post('/api/auth/login',base_url='https://localhost',json={'email':'admin@example.invalid','password':'fixture-only-password'})
                emit(sample=sample+1,path='login',status=response.status_code,total_ms=round((time.perf_counter()-start)*1000,2),stages_ms={k:round(v,2) for k,v in g.login_timings.items()})
            csrf=response.json['csrf_token']
            for path in ('/api/auth/me','/api/admin/dashboard'):
                start=time.perf_counter();response=client.get(path,base_url='https://localhost')
                emit(sample=sample+1,path=path,status=response.status_code,total_ms=round((time.perf_counter()-start)*1000,2),bytes=len(response.data))
            response=client.post('/api/auth/logout',base_url='https://localhost',headers={'X-CSRF-Token':csrf})
            assert response.status_code==200
            assert not client.get('/api/auth/me',base_url='https://localhost').json['authenticated']
        response=client.post('/api/auth/login',base_url='https://localhost',json={'email':'admin@example.invalid','password':'incorrect'})
        emit(path='invalid_login',status=response.status_code)
