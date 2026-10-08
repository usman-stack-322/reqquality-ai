"""Login performance regressions: isolated SQLite and mocked PostgreSQL only."""
import unittest
from unittest.mock import MagicMock, patch
import app
import test_admin_dashboard as fixtures
from services import auth_service, database_service, requirement_helpers


class LoginConnectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ManagerTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.ManagerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.client = app.app.test_client()

    def login(self, email, password=fixtures.PASSWORD):
        return self.client.post('/api/auth/login', json={'email': email, 'password': password})

    def test_admin_login_uses_one_connection_and_full_permissions(self):
        with patch.object(auth_service, 'get_connection', wraps=app.get_connection) as connect, patch.object(requirement_helpers, 'get_connection', side_effect=AssertionError('Unexpected second connection')):
            response = self.login('manager@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(connect.call_count, 1)
        self.assertEqual(response.json['user']['permissions'], list(fixtures.manager.PERMISSIONS))
        self.assertNotIn('password_hash', response.json['user'])
        self.assertIn('csrf_token', response.json)
        self.assertIn('connect;dur=', response.headers['Server-Timing'])
        self.assertIn('password;dur=', response.headers['Server-Timing'])
        from services.token_service import ACCESS_COOKIE, REFRESH_COOKIE
        self.assertIsNotNone(self.client.get_cookie(ACCESS_COOKIE, path='/api/'))
        self.assertIsNotNone(self.client.get_cookie(REFRESH_COOKIE, path='/api/auth/'))
        with self.client.session_transaction() as session:
            self.assertNotIn('user_id', session)

    def test_analyst_login_reuses_connection_and_observes_revoked_permissions(self):
        with patch.object(auth_service, 'get_connection', wraps=app.get_connection) as connect, patch.object(requirement_helpers, 'get_connection', side_effect=AssertionError('Unexpected second connection')):
            response = self.login('analyst@example.com')
            self.assertEqual(response.json['user']['permissions'], ['create_requirements'])
            self.fixture.sql("UPDATE role_permissions SET enabled=0 WHERE role='Analyst'")
            response = self.login('analyst@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['user']['permissions'], [])
        self.assertEqual(connect.call_count, 2)

    def test_invalid_credentials_do_not_create_session(self):
        for email, password in [('manager@example.com', 'wrong-password'), ('missing@example.com', fixtures.PASSWORD)]:
            with self.subTest(email=email):
                self.assertEqual(self.login(email, password).status_code, 401)
                with self.client.session_transaction() as session:
                    self.assertNotIn('user_id', session)

    def test_connection_is_closed_when_permission_lookup_fails(self):
        c = app.get_connection()
        with patch.object(auth_service, 'get_connection', return_value=c), patch.object(c, 'close', wraps=c.close) as close, patch.object(auth_service, '_public_user', side_effect=RuntimeError('lookup failed')):
            response = self.login('analyst@example.com')
            self.assertEqual(response.status_code, 500)
            close.assert_called_once()
            with self.client.session_transaction() as session:
                self.assertNotIn('user_id', session)


class PostgresInitializationTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock(dialect='postgres')
        for context in [
            patch.multiple(app, DATABASE_URL='postgresql://test-only', _POSTGRES_SCHEMA_URL=None),
            patch.object(database_service, 'connect_database', return_value=self.connection),
        ]:
            context.start()
            self.addCleanup(context.stop)
        self.schema = self.start_patch(database_service, 'initialize_postgresql_schema')
        self.management = self.start_patch(database_service, 'initialize_management_schema')
        self.invitations = self.start_patch(fixtures.invitations, 'initialize_invitations')

    def start_patch(self, module, name):
        context = patch.object(module, name)
        mock = context.start()
        self.addCleanup(context.stop)
        return mock

    def test_schema_and_invitation_initialization_run_once_per_database(self):
        database_service.get_connection()
        database_service.get_connection()
        for initializer in (self.schema, self.management, self.invitations):
            initializer.assert_called_once_with(self.connection)
        with patch.object(app, 'DATABASE_URL', 'postgresql://another-test-only'):
            database_service.get_connection()
        self.assertEqual(self.invitations.call_count, 2)

    def test_failed_initialization_closes_connection_and_retries(self):
        self.invitations.side_effect = [RuntimeError('migration failed'), None]
        with self.assertRaises(RuntimeError):
            database_service.get_connection()
        self.assertIsNone(app._POSTGRES_SCHEMA_URL)
        self.connection.close.assert_called_once()
        database_service.get_connection()
        self.assertEqual(self.invitations.call_count, 2)
        self.assertEqual(app._POSTGRES_SCHEMA_URL, 'postgresql://test-only')

    def test_warm_postgres_connection_executes_no_schema_sql(self):
        app._POSTGRES_SCHEMA_URL = app.DATABASE_URL
        database_service.get_connection()
        self.connection.execute.assert_not_called()
        self.schema.assert_not_called()
        self.management.assert_not_called()
        self.invitations.assert_not_called()


if __name__ == '__main__':
    unittest.main()
