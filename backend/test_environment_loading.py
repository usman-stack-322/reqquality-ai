"""Subprocess checks of actual entry points; no database connection or secret output."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


class EnvironmentLoadingTests(unittest.TestCase):
    def inspect(self, direct, inherited=None):
        env = os.environ.copy()
        env.pop('DATABASE_URL', None)
        if inherited is not None:
            env['DATABASE_URL'] = inherited
        env['REQQUALITY_SECRET_KEY'] = 'fixture-only-environment-key-32-bytes-long'
        env['JWT_SECRET_KEY'] = 'fixture-only-jwt-key-at-least-32-bytes-long'
        code = '''
import json,logging,runpy
from unittest.mock import patch
logging.disable(logging.CRITICAL)
with patch('flask.Flask.run'):
    if DIRECT:
        values=runpy.run_path('app.py',run_name='__main__')
    else:
        import app
        values=vars(app)
print(json.dumps({'source':values['DATABASE_CONFIG_SOURCE'],
                  'postgres':bool(values['DATABASE_URL']),
                  'local_http':values['LOCAL_HTTP_DEVELOPMENT']}))
'''.replace('DIRECT', repr(direct))
        result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).parent,
                                env=env, capture_output=True, text=True, timeout=15)
        # Never echo stderr: local environment may contain secrets.
        self.assertEqual(result.returncode, 0, 'Entry-point inspection failed; stderr withheld.')
        return json.loads(result.stdout)

    def test_explicit_empty_database_url_wins_in_both_entry_points(self):
        for direct in (True, False):
            with self.subTest(direct=direct):
                result = self.inspect(direct, '')
                self.assertEqual(result['source'], 'process environment')
                self.assertFalse(result['postgres'])
                self.assertEqual(result['local_http'], direct)

    def test_explicit_postgres_is_never_replaced_by_local_sqlite(self):
        for direct in (True, False):
            with self.subTest(direct=direct):
                result = self.inspect(direct, 'postgresql://fixture.invalid/test')
                self.assertEqual(result['source'], 'process environment')
                self.assertTrue(result['postgres'])

    def test_trust_proxy_hops_and_safe_startup_diagnostics_under_wsgi(self):
        env = os.environ.copy()
        secret_dsn = 'postgresql://hidden-user:hidden-password@ep-hidden-pooler.us-east-2.aws.neon.tech/hidden_db'
        env['DATABASE_URL'] = secret_dsn
        env['REQQUALITY_SECRET_KEY'] = 'fixture-only-environment-key-32-bytes-long'
        env['JWT_SECRET_KEY'] = 'fixture-only-jwt-key-at-least-32-bytes-long'
        env['TRUST_PROXY_HOPS'] = '1'
        env['FRONTEND_ORIGINS'] = 'https://www.reqqualityai.site/, https://reqqualityai.site/'
        env['COOKIE_SAMESITE'] = 'Lax'
        code = '''
import io, json, logging
stream = io.StringIO()
handler = logging.StreamHandler(stream)
logging.getLogger('app').addHandler(handler)
import app
client = app.app.test_client()
login_response = client.post(
    '/api/auth/login',
    base_url='http://reqquality-ai-api.onrender.com',
    headers={'X-Forwarded-Proto': 'https', 'X-Forwarded-For': '203.0.113.10', 'Origin': 'https://www.reqqualityai.site'},
    json={},
)
print(json.dumps({
    'origins': app.frontend_origins,
    'trust_proxy_hops': app.TRUST_PROXY_HOPS,
    'login_status': login_response.status_code,
    'logs': stream.getvalue(),
}))
'''
        result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).parent,
                                env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, 'WSGI startup inspection failed; stderr withheld.')
        payload = json.loads(result.stdout)
        self.assertEqual(payload['origins'], ['https://www.reqqualityai.site', 'https://reqqualityai.site'])
        self.assertEqual(payload['trust_proxy_hops'], 1)
        # X-Forwarded-Proto: https is honored under TRUST_PROXY_HOPS=1 (400 validation, not 426 HTTP rejection).
        self.assertEqual(payload['login_status'], 400)
        self.assertIn('mode=production_wsgi', payload['logs'])
        self.assertIn("'neon': True", payload['logs'])
        self.assertIn("'sslmode': 'require'", payload['logs'])
        for sensitive in ('hidden-user', 'hidden-password', 'ep-hidden', 'hidden_db', 'postgresql://'):
            self.assertNotIn(sensitive, payload['logs'])


if __name__ == '__main__':
    unittest.main()
