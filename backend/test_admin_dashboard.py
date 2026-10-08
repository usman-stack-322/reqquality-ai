"""Dashboard integration tests: temporary SQLite only; no SMTP or live database."""
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash
import app as application
from test_auth_helpers import authenticate
import admin_dashboard as manager
import invitations

PASSWORD = 'test-only-password-123'
HEADERS = {'X-CSRF-Token': 'test-csrf'}


class ManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = generate_password_hash(PASSWORD, method='scrypt')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(application, DATABASE_URL=None, DATABASE=Path(self.temp.name) / 'manager.db')
        self.settings.start()
        application.app.config.update(TESTING=True, SECRET_KEY='manager-tests-only', SESSION_COOKIE_SECURE=False)
        self.now = manager.utc_now()
        self.clock = patch.object(manager, 'utc_now', return_value=self.now)
        self.clock.start()
        self.sql("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)", ('Manager', 'manager@example.com', self.password_hash, 'admin'))
        for name, role in [('Analyst', 'Analyst'), ('Engineer', 'SQA Engineer'), ('Other Engineer', 'SQA Engineer')]:
            self.sql("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)", (name, name.replace(' ', '').lower()+'@example.com', self.password_hash, role))
        self.admin = self.client(1)

    def test_manager_promotion_and_permission_revocation(self):
        old_session = self.client(2)
        response = self.admin.patch('/api/admin/users/2', json={'role': 'Manager'}, headers=HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(old_session.get('/api/auth/me').get_json()['authenticated'])
        promoted = self.client()
        authenticate(promoted, 2, csrf='test-csrf', auth_version=1)
        self.assertEqual(promoted.get('/api/admin/dashboard').status_code, 200)
        self.assertEqual(promoted.get('/api/admin/roles').status_code, 200)
        self.assertEqual(promoted.patch('/api/admin/users/1', json={'role': 'Analyst'}, headers=HEADERS).status_code, 403)
        self.assertEqual(promoted.patch('/api/admin/users/2', json={'role': 'Analyst'}, headers=HEADERS).status_code, 403)
        with patch.object(invitations, 'send_invitation'):
            response = promoted.post('/api/admin/invitations', json={'name': 'New Manager', 'email': 'newmanager@example.com', 'role': 'Manager'}, headers=HEADERS)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.admin.patch('/api/admin/roles/Manager', json={'manage_invitations': False}, headers=HEADERS).status_code, 200)
        self.assertEqual(promoted.get('/api/admin/invitations').status_code, 403)
        self.assertEqual(self.admin.get('/api/admin/invitations').status_code, 200)
        self.assertEqual(promoted.patch('/api/admin/roles/Manager', json={'manage_permissions': False}, headers=HEADERS).status_code, 200)
        self.assertEqual(promoted.get('/api/admin/roles').status_code, 403)

    def test_role_permission_validation_and_csrf(self):
        self.assertEqual(self.admin.patch('/api/admin/roles/Manager', json={'manage_users': False}).status_code, 403)
        for role, data in [('admin', {'manage_users': False}), ('Manager', {'unknown': True}), ('Manager', {'manage_users': 'false'})]:
            self.assertEqual(self.admin.patch('/api/admin/roles/' + role, json=data, headers=HEADERS).status_code, 400)
        self.assertEqual(self.client(2).get('/api/admin/roles').status_code, 403)

    def tearDown(self):
        self.clock.stop()
        self.settings.stop()
        self.temp.cleanup()

    def sql(self, query, values=()):
        c = application.get_connection()
        try:
            with c:
                cursor = c.execute(query, values)
                return [dict(row) for row in cursor.fetchall()] if cursor.description else cursor.lastrowid
        finally:
            c.close()

    def client(self, user_id=None):
        client = application.app.test_client()
        if user_id:
            authenticate(client, user_id, csrf='test-csrf')
        return client

    def requirement(self, **changes):
        row = dict(title='Account validation', description='Validate the supplied details.', requirement_type='Functional',
                   priority='Medium', risk_level=None, risk_score=None, review_status='Pending',
                   created_at=self.now.isoformat(), updated_at=self.now.isoformat(), created_by_user_id=2,
                   assigned_reviewer_user_id=None, analysis_summary='{}', reviewed_by_user_id=None, reviewed_at=None)
        row.update(changes)
        return self.sql(f"INSERT INTO requirements({','.join(row)}) VALUES({','.join('?' for _ in row)})", tuple(row.values()))

    def criteria(self, requirement_id, code='AC-1'):
        self.sql('INSERT INTO requirement_acceptance_criteria(requirement_id,criterion_code,description) VALUES(?,?,?)', (requirement_id, code, 'Valid credentials succeed.'))

    def scenario(self, requirement_id, code='TS-1'):
        self.sql("INSERT INTO test_scenarios(requirement_id,scenario_code,category,title,preconditions,test_steps,expected_result) VALUES(?,?,'Positive','Successful login','[]','[]','Account opens')", (requirement_id, code))

    def dashboard(self, **filters):
        response = self.admin.get('/api/admin/dashboard', query_string=filters)
        self.assertEqual(response.status_code, 200, response.json)
        return response.json

    def test_empty_dashboard_and_legacy_api(self):
        data = self.dashboard()
        self.assertEqual(data['summary']['total'], 0)
        self.assertEqual(data['traceability']['coverage'], 0)
        self.assertEqual(data['attention'], [])
        self.assertEqual(data['pending_reviews'], [])
        self.assertEqual(data['activity'], [])
        self.assertEqual(data['invitations']['pending'], 0)
        self.assertEqual(self.admin.get('/api/dashboard').status_code, 200)

    def test_all_admin_endpoints_enforce_roles(self):
        endpoints = [('GET', '/api/admin/dashboard', None), ('GET', '/api/admin/requirements', None),
                     ('PATCH', '/api/admin/settings', {'name': 'New org', 'overdue_days': 7}),
                     ('PATCH', '/api/admin/users/2', {'is_active': False}),
                     ('PATCH', '/api/admin/requirements/1/reviewer', {'reviewer_id': 3})]
        for user_id, expected in [(None, 401), (2, 403), (3, 403)]:
            for method, url, body in endpoints:
                with self.subTest(user=user_id, endpoint=url):
                    self.assertEqual(self.client(user_id).open(url, method=method, json=body, headers=HEADERS).status_code, expected)

    def test_csrf_on_management_mutations(self):
        for url, body in [('/api/admin/settings', {'name': 'Test', 'overdue_days': 7}), ('/api/admin/users/2', {'is_active': False}), ('/api/admin/requirements/1/reviewer', {'reviewer_id': 3})]:
            self.assertEqual(self.admin.patch(url, json=body).status_code, 403)
        self.assertEqual(self.admin.post('/api/auth/change-password', json={}).status_code, 403)

    def test_real_counts_child_aggregation_and_workload(self):
        first = self.requirement(title='Critical access', risk_level='Critical', risk_score=90, created_at=(self.now-timedelta(days=8)).isoformat(), analysis_summary=json.dumps({'ambiguity_issues': ['Unclear wording']}))
        second = self.requirement(risk_level='High', risk_score=65, review_status='In Review', assigned_reviewer_user_id=3, analysis_summary=json.dumps({'missing_information': ['No timeout']}))
        third = self.requirement(risk_level='Low', risk_score=10, review_status='Approved', assigned_reviewer_user_id=3, reviewed_by_user_id=3, reviewed_at=self.now.isoformat())
        self.requirement(risk_level='Medium', risk_score=40, review_status='Needs Revision', assigned_reviewer_user_id=4)
        self.requirement(analysis_summary='invalid JSON')
        for _id in (second, third):
            self.criteria(_id)
            self.scenario(_id)
        self.criteria(third, 'AC-2')
        self.scenario(third, 'TS-2')
        data = self.dashboard()
        self.assertEqual(data['summary'], dict(total=5, analyzed=4, pending_reviews=3, approved=1, high_risk=2, needs_revision=1, unassigned=2, overdue=1))
        self.assertEqual(data['traceability'], dict(with_criteria=2, with_tests=2, reviewed=1, fully_traceable=2, missing_links=3, coverage=40.0))
        self.assertEqual(data['quality']['ambiguity'], 1)
        self.assertEqual(data['quality']['missing_information'], 1)
        self.assertFalse(data['conflicts_available'])
        self.assertEqual(data['attention'][0]['id'], first)
        self.assertEqual(data['pending_reviews'][0]['id'], first)
        self.assertEqual(data['review_distribution'][0]['percent'], 40)
        self.assertEqual(data['unscored'], 1)
        engineer = next(row for row in data['reviewer_workload'] if row['id'] == 3)
        self.assertEqual([engineer[key] for key in ('assigned', 'pending', 'completed', 'high_risk')], [2, 1, 1, 1])

    def test_filters_pagination_and_search(self):
        first = self.requirement(title='Payment audit', risk_level='High', risk_score=70, requirement_type='Business', assigned_reviewer_user_id=3)
        self.criteria(first)
        self.requirement(title='Session timeout', risk_level='Low', review_status='Approved', created_at=(self.now-timedelta(days=30)).isoformat())
        filters = [{'risk': 'high-critical'}, {'type': 'Business'}, {'reviewer': '3'}, {'q': 'PAYMENT'}, {'q': f'REQ-{first}'}, {'review': 'pending-reviews'}, {'quality': 'has_criteria'}, {'from': self.now.date().isoformat()}]
        for values in filters:
            with self.subTest(filters=values):
                self.assertEqual(self.dashboard(**values)['summary']['total'], 1)
        response = self.admin.get('/api/admin/requirements?page_size=1&page=2')
        self.assertEqual(response.json['total'], 2)
        self.assertEqual(response.json['requirements'][0]['id'], first)
        self.assertEqual(self.dashboard(project='current')['summary']['total'], 2)
        self.assertEqual(self.dashboard(reviewer='unassigned')['summary']['total'], 1)
        self.assertEqual(self.dashboard(quality='has_tests')['summary']['total'], 0)

    def test_invalid_filters_rejected(self):
        for values in [{'risk': "High' OR 1=1"}, {'review': 'Rejected'}, {'type': 'Other'}, {'from': '2026-99-01'}, {'from': '2026-1-1'}, {'from': '2026-10-02', 'to': '2026-01-01'}, {'reviewer': '-1'}, {'reviewer': '\u00b2'}, {'page_size': '1000'}, {'page': '0'}, {'project': 'other'}, {'q': 'x'*201}, {'unexpected': 'value'}]:
            with self.subTest(filters=values):
                self.assertEqual(self.admin.get('/api/admin/dashboard', query_string=values).status_code, 400)

    def test_assign_reassign_unassign_and_audit(self):
        _id = self.requirement()
        for assignee in (3, 4, None):
            response = self.admin.patch(f'/api/admin/requirements/{_id}/reviewer', json={'reviewer_id': assignee}, headers=HEADERS)
            self.assertEqual(response.status_code, 200, response.json)
            row = self.sql('SELECT assigned_reviewer_user_id,reviewed_by_user_id,review_status FROM requirements WHERE id=?', (_id,))[0]
            self.assertEqual(row['assigned_reviewer_user_id'], assignee)
            self.assertIsNone(row['reviewed_by_user_id'])
            self.assertEqual(row['review_status'], 'Pending')
        self.assertEqual(len(self.dashboard()['activity']), 3)
        self.assertEqual(self.admin.get(f'/api/requirements/{_id}').json['requirement']['assigned_reviewer'], None)

    def test_assignment_validation(self):
        _id = self.requirement()
        self.sql('UPDATE users SET is_active=0 WHERE id=4')
        for reviewer in (1, 2, 4, 999, True, '3', -1):
            self.assertEqual(self.admin.patch(f'/api/admin/requirements/{_id}/reviewer', json={'reviewer_id': reviewer}, headers=HEADERS).status_code, 400)
        self.assertEqual(self.admin.patch('/api/admin/requirements/999/reviewer', json={'reviewer_id': 3}, headers=HEADERS).status_code, 404)

    def test_disable_revokes_sessions_and_clears_only_open_assignments(self):
        pending = self.requirement(assigned_reviewer_user_id=3)
        approved = self.requirement(assigned_reviewer_user_id=3, review_status='Approved', reviewed_by_user_id=3, reviewed_at=self.now.isoformat())
        engineer = self.client(3)
        self.assertTrue(engineer.get('/api/auth/me').json['authenticated'])
        self.assertEqual(self.admin.patch('/api/admin/users/3', json={'is_active': False}, headers=HEADERS).status_code, 200)
        self.assertFalse(engineer.get('/api/auth/me').json['authenticated'])
        self.assertEqual(engineer.post('/api/auth/login', json={'email': 'engineer@example.com', 'password': PASSWORD}).status_code, 401)
        self.assertIsNone(self.sql('SELECT assigned_reviewer_user_id FROM requirements WHERE id=?', (pending,))[0]['assigned_reviewer_user_id'])
        self.assertEqual(self.sql('SELECT assigned_reviewer_user_id FROM requirements WHERE id=?', (approved,))[0]['assigned_reviewer_user_id'], 3)
        self.admin.patch('/api/admin/users/3', json={'is_active': True}, headers=HEADERS)
        self.assertFalse(engineer.get('/api/auth/me').json['authenticated'])
        self.assertEqual(engineer.post('/api/auth/login', json={'email': 'engineer@example.com', 'password': PASSWORD}).status_code, 200)

    def test_role_change_and_admin_protection(self):
        engineer = self.client(3)
        self.requirement(assigned_reviewer_user_id=3)
        self.assertEqual(self.admin.patch('/api/admin/users/3', json={'role': 'Analyst'}, headers=HEADERS).status_code, 200)
        self.assertEqual(engineer.get('/api/dashboard').status_code, 401)
        self.assertEqual(self.dashboard()['team_summary']['engineers'], 1)
        for body in ({'role': 'admin'}, {'role': 'Super Admin'}, {'is_active': 0}, {'email': 'other@example.com'}):
            self.assertEqual(self.admin.patch('/api/admin/users/2', json=body, headers=HEADERS).status_code, 400)
        self.assertEqual(self.admin.patch('/api/admin/users/1', json={'is_active': False}, headers=HEADERS).status_code, 403)

    def test_settings_overdue_threshold(self):
        self.requirement(created_at=(self.now-timedelta(days=5)).isoformat())
        self.assertEqual(self.dashboard()['summary']['overdue'], 0)
        response = self.admin.patch('/api/admin/settings', json={'name': 'Example Quality', 'overdue_days': 3}, headers=HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.dashboard()['organization']['name'], 'Example Quality')
        self.assertEqual(self.dashboard()['summary']['overdue'], 1)
        self.assertEqual(self.admin.patch('/api/admin/settings', json={'name': 'X', 'overdue_days': 0}, headers=HEADERS).status_code, 400)

    def test_password_change_invalidates_other_sessions(self):
        other = self.client(1)
        url = '/api/auth/change-password'
        self.assertEqual(self.admin.post(url, json={'current_password': 'wrong', 'new_password': PASSWORD+'new'}, headers=HEADERS).status_code, 400)
        self.assertEqual(self.admin.post(url, json={'current_password': PASSWORD, 'new_password': 'short'}, headers=HEADERS).status_code, 400)
        self.assertEqual(self.admin.post(url, json={'current_password': PASSWORD, 'new_password': PASSWORD+'new'}, headers=HEADERS).status_code, 200)
        self.assertEqual(other.get('/api/admin/dashboard').status_code, 401)
        self.assertEqual(self.admin.get('/api/admin/dashboard').status_code, 401)
        self.assertEqual(self.admin.post('/api/auth/login', json={'email': 'manager@example.com', 'password': PASSWORD+'new'}).status_code, 200)

    def test_invitation_counts_expiry_and_no_sensitive_fields(self):
        with patch.object(invitations, 'send_invitation'):
            for index in range(4):
                response = self.admin.post('/api/admin/invitations', json={'name': 'Invite Person', 'email': f'invite{index}@example.com', 'role': 'Analyst'}, headers=HEADERS)
                self.assertEqual(response.status_code, 201)
        self.sql("UPDATE user_invitations SET expires_at=? WHERE id=2", ((self.now-timedelta(seconds=1)).isoformat(),))
        self.sql("UPDATE user_invitations SET status='accepted' WHERE id=3")
        self.sql("UPDATE user_invitations SET status='revoked' WHERE id=4")
        data = self.dashboard()
        self.assertEqual(data['invitations'], dict(pending=1, expired=1, accepted=1, revoked=1))
        self.assertEqual(len(data['invited_members']), 1)
        for secret in ('password_hash', 'token_hash', 'auth_version', 'csrf_token', 'temporarily_locked_until'):
            self.assertNotIn(secret, json.dumps(data))

    def test_existing_requirement_and_review_flow_records_activity(self):
        analyst = self.client(2)
        response = analyst.post('/api/requirements', json={'title': 'Secure account access', 'description': 'The system shall validate account credentials.', 'requirement_type': 'Functional', 'priority': 'High'}, headers=HEADERS)
        self.assertEqual(response.status_code, 201, response.json)
        _id = response.json['requirement']['id']
        self.assertEqual(self.admin.patch(f'/api/requirements/{_id}/review', json={'review_status': 'Approved'}, headers=HEADERS).status_code, 403)
        response = self.client(3).patch(f'/api/requirements/{_id}/review', json={'review_status': 'Approved'}, headers=HEADERS)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(self.dashboard()['summary']['approved'], 1)
        self.assertEqual({row['action'] for row in self.dashboard()['activity']}, {'requirement_created', 'review_updated'})

    def test_bounded_attention_and_activity_and_idempotent_migration(self):
        for index in range(12):
            self.requirement(title=f'Requirement {index}')
        data = self.dashboard()
        self.assertEqual(data['attention_total'], 12)
        self.assertEqual(len(data['attention']), 8)
        self.assertEqual(len(data['pending_reviews']), 8)
        self.assertEqual(self.sql('SELECT COUNT(*) AS count FROM organization_settings')[0]['count'], 1)

    def test_no_users_projection_and_nullable_analysis(self):
        self.sql('DELETE FROM users')
        c = application.get_connection()
        try:
            result = manager.build_dashboard(c, manager.parse_filters({}))
        finally:
            c.close()
        self.assertEqual(result['team'], [])
        self.assertEqual(result['reviewer_workload'], [])
        self.assertEqual(result['team_summary']['active'], 0)

    def test_malformed_analysis_does_not_break_existing_detail(self):
        _id = self.requirement(analysis_summary='invalid JSON')
        response = self.admin.get(f'/api/requirements/{_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['requirement']['analysis_summary'], {})
        self.assertEqual(self.dashboard()['summary']['analyzed'], 0)

    def test_creation_date_boundaries_and_overdue_exact_threshold(self):
        self.requirement(created_at=(self.now-timedelta(days=7)).isoformat())
        self.requirement(created_at=self.now.isoformat())
        date = self.now.date().isoformat()
        self.assertEqual(self.dashboard(**{'from': date, 'to': date})['summary']['total'], 1)
        self.assertEqual(self.dashboard()['summary']['overdue'], 1)


if __name__ == '__main__':
    unittest.main()
