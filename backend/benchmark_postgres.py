"""Read-only hosted-database diagnostic. No migrations, email, or successful login."""
import time,json
import app
from database import connect_database,close_database_pools
from psycopg.pq import TransactionStatus

try:
 for i in range(4):
  start=time.perf_counter();c=connect_database(app.DATABASE_URL,app.DATABASE);opened=time.perf_counter()
  with c.autocommit_reads():
   c.execute('SELECT 1').fetchone()
  queried=time.perf_counter();c.close();ended=time.perf_counter()
  print(json.dumps({'sample':i+1,'connect_ms':round((opened-start)*1000,1),'read_ms':round((queried-opened)*1000,1),'close_ms':round((ended-queried)*1000,1)}))
 # Verify real pooled transaction rollback without persistent schema or row changes.
 c=connect_database(app.DATABASE_URL,app.DATABASE)
 try:
  try:
   with c:
    c.execute('CREATE TEMP TABLE pool_rollback_probe(value INTEGER) ON COMMIT DROP')
    c.execute('INSERT INTO pool_rollback_probe VALUES (1)')
    raise ValueError('intentional rollback')
  except ValueError:
   pass
  assert c._connection.info.transaction_status==TransactionStatus.IDLE
  with c.autocommit_reads():
   assert c.execute("SELECT to_regclass('pg_temp.pool_rollback_probe') AS table_name").fetchone()['table_name'] is None
  print('Real pooled PostgreSQL transaction rollback verified')
 finally:
  c.close()
 # Authenticate with a known-invalid password to measure hashing without creating a session.
 c=connect_database(app.DATABASE_URL,app.DATABASE)
 try:
  with c.autocommit_reads():
   user=c.execute("SELECT email FROM users WHERE role='admin' AND is_active=1 ORDER BY id LIMIT 1").fetchone()
 finally:
  c.close()
 if user:
  app._POSTGRES_SCHEMA_URL=app.DATABASE_URL  # Diagnostic explicitly skips migrations.
  app.LOGGER.disabled=True
  client=app.app.test_client()
  for i in range(3):
   start=time.perf_counter()
   response=client.post('/api/auth/login',base_url='https://localhost',json={'email':user['email'],'password':'invalid-benchmark-password-not-a-credential'})
   assert response.status_code==401
   print(json.dumps({'invalid_password_login_ms':round((time.perf_counter()-start)*1000,1),'server_timing':response.headers.get('Server-Timing')}))
finally:
 close_database_pools()
