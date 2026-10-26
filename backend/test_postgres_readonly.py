"""Safety regressions for the opt-in PostgreSQL verification tool."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app
import psycopg
import verify_postgres_readonly as probe


class ReadonlyProbeSafetyTests(unittest.TestCase):
    def run_probe(self, url, error=None):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'result.json'
            stdout=StringIO()
            with patch.object(app,'DATABASE_URL',url), patch('sys.argv',['probe','--output',str(output)]), patch('logging.disable'), patch('database.connect_database',side_effect=error or AssertionError('SQLite must never be opened')) as connect, redirect_stdout(stdout):
                status=probe.main()
            return status,json.loads(output.read_text()),stdout.getvalue(),connect.call_count

    def test_missing_postgres_configuration_never_falls_back_to_sqlite(self):
        status,data,_,calls=self.run_probe(None)
        self.assertEqual(status,1)
        self.assertEqual(calls,0)
        self.assertIn('SQLite was not opened',data['blocked'])

    def test_connection_failure_output_never_exposes_driver_credentials(self):
        status,data,text,calls=self.run_probe('postgresql://test-only',psycopg.OperationalError('postgresql://private-user:private-password@private-host/private-db'))
        self.assertEqual(status,1)
        self.assertEqual(calls,1)
        self.assertFalse(data['connection_checks_passed'])
        for private in ('private-user','private-password','private-host','private-db','postgresql://'):
            self.assertNotIn(private,text)


if __name__=='__main__':
    unittest.main()
