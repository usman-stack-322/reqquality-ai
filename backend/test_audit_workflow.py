"""Authorization and complete workflow regressions; temporary SQLite, mocked AI/SMTP."""
import json
from io import BytesIO
import unittest
from pypdf import PdfReader
from unittest.mock import patch
import app
import test_admin_dashboard as fixtures
from services import auth_service, rate_limit_service


class AuditWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ManagerTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.ManagerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.admin = self.fixture.admin
        self.analyst = self.fixture.client(2)
        self.engineer = self.fixture.client(3)
        self.guest = self.fixture.client()
        self.headers = fixtures.HEADERS
        self.payload = {'title': 'Sign in', 'description': 'A registered user can sign in using valid credentials.',
                        'requirement_type': 'Functional', 'priority': 'Medium'}

    def test_requirement_to_review_and_exports_with_ai_network_failure(self):
        with patch('analyzers.hybrid_analyzer.analyze_with_llm', side_effect=TimeoutError), patch('analyzers.test_scenario_generator._generate_with_gemini', return_value=[]):
            response = self.analyst.post('/api/analyze-requirement', json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.json)
        analysis = response.json
        self.assertEqual(analysis['analysis_mode'], 'rule_based_only')
        self.assertEqual(analysis['llm_status'], 'api_error')
        self.assertTrue(analysis['improved_requirement'])
        self.assertTrue(analysis['acceptance_criteria'])
        self.assertEqual({s['category'] for s in analysis['test_scenarios']}, {'Positive', 'Negative', 'Boundary', 'Edge-case'})
        saved = self.analyst.post('/api/requirements', json={**self.payload, 'analysis': analysis}, headers=self.headers)
        self.assertEqual(saved.status_code, 201, saved.json)
        rid = saved.json['requirement']['id']
        record = self.engineer.get(f'/api/requirements/{rid}').json['requirement']
        self.assertEqual(record['created_by_user_id'], 2)
        self.assertEqual(record['analysis_summary']['improved_requirement'], analysis['improved_requirement'])
        self.assertTrue(record['test_scenarios'])
        self.assertTrue(record['acceptance_criteria'])
        for status in ['In Review', 'Needs Revision', 'Approved']:
            reviewed = self.engineer.patch(f'/api/requirements/{rid}/review', json={'review_status': status, 'reviewer_notes': 'Human review recorded.'}, headers=self.headers)
            self.assertEqual(reviewed.status_code, 200, reviewed.json)
            self.assertEqual(reviewed.json['requirement']['reviewed_by_user_id'], 3)
        self.assertEqual(self.analyst.get('/api/dashboard').json['approved_count'], 1)
        self.assertEqual(self.admin.get('/api/admin/dashboard').json['summary']['approved'], 1)
        self.assertEqual(self.analyst.get('/api/dashboard').json['traceability_coverage_percent'], 100)
        for client in [self.admin, self.analyst, self.engineer]:
            for path in [f'/api/requirements/{rid}/report.pdf', '/api/reports/project.pdf']:
                export = client.get(path)
                self.assertEqual(export.status_code, 200)
                self.assertEqual(export.mimetype, 'application/pdf')
                self.assertTrue(export.data.startswith(b'%PDF-'))
                self.assertIn(b'%%EOF', export.data[-100:])
                self.assertIn('attachment', export.headers['Content-Disposition'])
                pdf = PdfReader(BytesIO(export.data), strict=True)
                self.assertGreater(len(pdf.pages), 0)
                text = '\n'.join(page.extract_text() for page in pdf.pages)
                self.assertIn('ReqQuality AI', text)
                if '/requirements/' in path:
                    self.assertIn('Sign in', text)
                    self.assertIn('Human review recorded.', text)
            csv = client.get('/api/exports/requirements.csv')
            self.assertEqual(csv.status_code, 200)
            self.assertIn('Sign in', csv.data.decode('utf-8-sig'))

    def test_server_side_permissions_and_shared_record_scope(self):
        rid = self.fixture.requirement(assigned_reviewer_user_id=4)
        # Assignment is a workload aid, not an existing per-record access restriction.
        for client in [self.admin, self.analyst, self.engineer]:
            self.assertEqual(client.get(f'/api/requirements/{rid}').status_code, 200)
        for path in ['/api/requirements', f'/api/requirements/{rid}', '/api/dashboard', '/api/admin/dashboard', '/api/exports/requirements.csv', '/api/reports/project.pdf', f'/api/requirements/{rid}/report.pdf']:
            self.assertEqual(self.guest.get(path).status_code, 401)
        self.assertEqual(self.analyst.patch(f'/api/requirements/{rid}/review', json={'review_status': 'Approved'}, headers=self.headers).status_code, 403)
        self.assertEqual(self.admin.patch(f'/api/requirements/{rid}/review', json={'review_status': 'Approved'}, headers=self.headers).status_code, 403)
        self.assertEqual(self.admin.post('/api/requirements', json=self.payload, headers=self.headers).status_code, 403)
        self.assertEqual(self.engineer.post('/api/requirements', json=self.payload, headers=self.headers).status_code, 403)
        self.assertEqual(self.engineer.post('/api/analyze-requirement', json=self.payload, headers=self.headers).status_code, 403)
        self.assertEqual(self.analyst.post('/api/requirements', json=self.payload).status_code, 403)
        self.fixture.sql("UPDATE role_permissions SET enabled=0 WHERE role='SQA Engineer' AND permission='review_requirements'")
        self.assertEqual(self.engineer.patch(f'/api/requirements/{rid}/review', json={'review_status': 'Approved'}, headers=self.headers).status_code, 403)

    def test_login_limit_persists_across_clients_and_recovers(self):
        with patch.object(rate_limit_service.time, 'time', return_value=1800000000), patch.object(auth_service, 'check_password_hash', return_value=False):
            for _ in range(10):
                self.assertEqual(self.fixture.client().post('/api/auth/login', json={'email': 'analyst@example.com', 'password': 'wrong'}).status_code, 401)
            response = self.fixture.client().post('/api/auth/login', json={'email': ' ANALYST@example.com ', 'password': 'wrong'})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers['Retry-After'], '900')
        with patch.object(rate_limit_service.time, 'time', return_value=1800000900), patch.object(auth_service, 'check_password_hash', return_value=False):
            self.assertEqual(self.guest.post('/api/auth/login', json={'email': 'analyst@example.com', 'password': 'wrong'}).status_code, 401)
        rows = self.fixture.sql('SELECT * FROM request_limits')
        self.assertNotIn('analyst@example.com', json.dumps(rows))

    def test_reset_limits_before_password_hashing(self):
        with patch('services.password_reset_service.send_reset_email'):
            for _ in range(5):
                self.assertEqual(self.guest.post('/api/auth/forgot-password', json={'email': 'missing@example.com'}).status_code, 200)
            self.assertEqual(self.guest.post('/api/auth/forgot-password', json={'email': 'missing@example.com'}).status_code, 429)
        self.fixture.sql('DELETE FROM request_limits')
        with patch('services.password_reset_service.generate_password_hash', return_value='test-only-hash') as hash_password:
            for _ in range(20):
                self.assertEqual(self.guest.post('/api/auth/reset-password', json={'token': 'x'*40, 'password': fixtures.PASSWORD}).status_code, 400)
            self.assertEqual(self.guest.post('/api/auth/reset-password', json={'token': 'x'*40, 'password': fixtures.PASSWORD}).status_code, 429)
            self.assertEqual(hash_password.call_count, 20)

    def test_summary_omits_analysis_and_full_response_remains_compatible(self):
        self.fixture.requirement(analysis_summary=json.dumps({'improved_requirement': 'x'*10000}))
        full = self.analyst.get('/api/requirements')
        short = self.analyst.get('/api/requirements?view=summary')
        self.assertIn('analysis_summary', full.json['requirements'][0])
        self.assertNotIn('analysis_summary', short.json['requirements'][0])
        self.assertEqual(short.json['requirements'][0]['id'], full.json['requirements'][0]['id'])
        self.assertLess(len(short.data), len(full.data)/10)

    def test_session_reuses_connection_and_permissions_are_fresh(self):
        with patch('services.requirement_helpers.get_connection', side_effect=AssertionError('Duplicate session connection')):
            response = self.analyst.get('/api/auth/me')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['authenticated'])
        self.fixture.sql("UPDATE role_permissions SET enabled=0 WHERE role='Analyst'")
        self.assertEqual(self.analyst.get('/api/auth/me').json['user']['permissions'], [])
        self.assertIn('db_connect;dur=', response.headers['Server-Timing'])
        self.assertIn('db_execute;dur=', response.headers['Server-Timing'])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertNotIn('password_hash', response.json['user'])

    def test_input_bounds_unhashable_values_origin_and_sql_safety(self):
        for analysis in [{'risk_level': []}, {'suggested_priority': {}}, {'test_scenarios': [{'category': []}]}, {'assumptions': 42}, {'improved_requirement': []}, {'test_scenarios': [{'id': {}, 'category': 'Positive'}]}]:
            self.assertEqual(self.analyst.post('/api/requirements', json={**self.payload, 'analysis': analysis}, headers=self.headers).status_code, 400)
        self.assertEqual(self.analyst.post('/api/requirements', json={**self.payload, 'description': 'x'*20001}, headers=self.headers).status_code, 400)
        self.assertEqual(self.guest.post('/api/auth/login', json={}, headers={'Origin': 'https://attacker.example'}).status_code, 403)
        response = self.analyst.post('/api/requirements', json=self.payload, headers={**self.headers, 'Origin': 'https://localhost'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(self.guest.post('/api/auth/login', data='x'*(1024*1024+1), content_type='application/json').status_code, 413)
        with patch.object(auth_service, 'check_password_hash', return_value=False):
            self.assertEqual(self.guest.post('/api/auth/login', json={'email': "' OR 1=1 --", 'password': 'x'}).status_code, 401)

    def test_csv_formula_escaping_and_literal_xss_input(self):
        self.fixture.requirement(title='  =HYPERLINK("https://example.com")')
        response = self.analyst.get('/api/exports/requirements.csv')
        self.assertIn("'  =HYPERLINK", response.data.decode('utf-8-sig'))
        saved = self.analyst.post('/api/requirements', json={**self.payload, 'title': '<script>alert(1)</script>'}, headers=self.headers)
        self.assertEqual(saved.status_code, 201)
        self.assertEqual(saved.json['requirement']['title'], '<script>alert(1)</script>')


if __name__ == '__main__':
    unittest.main()
