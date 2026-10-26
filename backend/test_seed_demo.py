"""Demo seed integrity, preservation and rollback on disposable SQLite."""
import unittest
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import test_admin_dashboard as fixtures
from seed_demo import seed


class DemoSeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ManagerTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.ManagerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def run_seed(self, owner=2, reviewer=3):
        import app
        c = app.get_connection()
        try:
            return seed(c, owner, reviewer)
        finally:
            c.close()

    def test_rerun_preserves_existing_content_users_and_relationships(self):
        existing = self.fixture.requirement(title='Existing real work')
        self.assertEqual(self.run_seed(), {'created': 4, 'skipped': 0})
        self.fixture.sql("UPDATE requirements SET title='Edited demo' WHERE title='[DEMO] Fast search'")
        self.assertEqual(self.run_seed(), {'created': 0, 'skipped': 4})
        self.assertEqual(len(self.fixture.sql('SELECT id FROM users')), 4)
        self.assertEqual(len(self.fixture.sql('SELECT id FROM requirements')), 5)
        self.assertEqual(self.fixture.sql('SELECT title FROM requirements WHERE id=?', (existing,))[0]['title'], 'Existing real work')
        self.assertEqual(len(self.fixture.sql("SELECT id FROM requirements WHERE title='Edited demo'")), 1)
        self.assertEqual(self.fixture.sql('PRAGMA foreign_key_check'), [])
        self.assertEqual(len(self.fixture.sql('SELECT id FROM requirement_reviews')), 2)
        self.assertEqual(len(self.fixture.sql('SELECT id FROM test_case_versions')), 4)
        import app
        self.assertTrue(all(row['category'] in app.SCENARIO_CATEGORIES for row in self.fixture.sql('SELECT category FROM test_scenarios')))
        client = self.fixture.client(3)
        dashboard = client.get('/api/dashboard').json
        self.assertEqual(dashboard['requirements_with_linked_cases'], 4)
        self.assertEqual(dashboard['latest_execution_counts']['Not Run'], 4)
        rid = self.fixture.sql("SELECT id FROM requirements WHERE title='[DEMO] Owned support ticket'")[0]['id']
        report = client.get(f'/api/requirements/{rid}/report.pdf')
        self.assertEqual(report.status_code, 200)
        for stage in ('report_data', 'report_render', 'report_response'):
            self.assertIn(stage + ';dur=', report.headers['Server-Timing'])
        self.assertEqual(report.mimetype, 'application/pdf')
        self.assertIn(f'reqquality-requirement-{rid}.pdf', report.headers['Content-Disposition'])
        self.assertEqual(client.get(f'/api/requirements/{rid}/traceability').status_code, 200)

    def test_invalid_accounts_leave_no_demo_content(self):
        for owner, reviewer in ((3, 2), (999, 3), (2, 1)):
            with self.assertRaises(ValueError):
                self.run_seed(owner, reviewer)
        self.assertEqual(self.fixture.sql('SELECT id FROM requirements'), [])

    def test_existing_non_demo_receipt_collision_is_not_silently_skipped(self):
        self.fixture.sql('INSERT INTO requirement_submissions(user_id,request_key,input_hash) VALUES(?,?,?)', (2, 'demo-v1-clear', 'existing-real-submission'))
        with self.assertRaises(ValueError):
            self.run_seed()
        self.assertEqual(self.fixture.sql('SELECT id FROM requirements'), [])

    def test_mid_seed_failure_rolls_back_all_records(self):
        with patch('services.case_service.register_generated_cases', side_effect=RuntimeError('synthetic failure')):
            with self.assertRaises(RuntimeError):
                self.run_seed()
        for table in ('requirements', 'test_scenarios', 'requirement_acceptance_criteria', 'requirement_submissions'):
            self.assertEqual(self.fixture.sql('SELECT * FROM ' + table), [])

    def test_explicit_cli_ignores_configured_cloud_target_and_is_repeatable(self):
        import app
        script = Path(__file__).with_name('seed_demo.py')
        command = [sys.executable, str(script), '--sqlite', str(app.DATABASE), '--owner-id', '2', '--reviewer-id', '3']
        with patch.dict('os.environ', DATABASE_URL='postgresql://unused.invalid/never-connect'):
            for expected in ({'created': 4, 'skipped': 0}, {'created': 0, 'skipped': 4}):
                result = subprocess.run(command, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                output = json.loads(result.stdout)
                self.assertEqual({key: output[key] for key in expected}, expected)
        self.assertEqual(self.fixture.sql('PRAGMA foreign_key_check'), [])


if __name__ == '__main__':
    unittest.main()
