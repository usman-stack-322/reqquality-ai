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


if __name__ == '__main__':
    unittest.main()
