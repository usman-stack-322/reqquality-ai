"""Outages return safe errors without authenticating or discarding sessions."""
import unittest
from unittest.mock import patch
from psycopg_pool import PoolTimeout, TooManyRequests, PoolClosed
import psycopg
import app
import test_admin_dashboard as fixtures


class DatabaseUnavailableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ManagerTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.ManagerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.client = self.fixture.admin

    def test_login_outage_is_not_invalid_credentials_and_leaks_no_details(self):
        for exception in [PoolTimeout('private connection info'), TooManyRequests('private connection info'), PoolClosed('private connection info'),
                          psycopg.OperationalError('private connection info'),
                          psycopg.errors.QueryCanceled('private connection info'),
                          psycopg.errors.LockNotAvailable('private connection info')]:
            with patch('services.auth_service.get_connection', side_effect=exception), self.assertLogs(app.app.logger, level='ERROR') as logs:
                response = self.client.post('/api/auth/login', json={'email': 'manager@example.com', 'password': fixtures.PASSWORD})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json['code'], 'database_unavailable')
            self.assertEqual(response.headers['Retry-After'], '30')
            self.assertFalse(response.headers.getlist('Set-Cookie'))
            self.assertNotIn('private connection info', str(response.json) + str(logs.output))

    def test_session_and_dashboard_outages_preserve_existing_session(self):
        with patch('middlewares.auth.get_connection', side_effect=PoolTimeout('private connection info')):
            for path in ['/api/auth/me', '/api/admin/dashboard', '/api/dashboard']:
                response = self.client.get(path)
                self.assertEqual(response.status_code, 503, path)
                self.assertEqual(response.json['code'], 'database_unavailable')
                self.assertFalse(response.headers.getlist('Set-Cookie'))
        self.assertTrue(self.client.get('/api/auth/me').json['authenticated'])

    def test_invalid_credentials_stay_generic(self):
        response = self.client.post('/api/auth/login', json={'email': 'manager@example.com', 'password': 'wrong'})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json['error'], 'Email or password is incorrect.')

    def test_query_timeout_releases_connection_and_preserves_existing_session(self):
        c = app.get_connection()
        with patch('services.auth_service.get_connection', return_value=c), patch.object(c, 'close', wraps=c.close) as close, patch.object(c, 'execute', side_effect=psycopg.errors.QueryCanceled('private query text')):
            response = self.client.post('/api/auth/login', json={'email': 'manager@example.com', 'password': fixtures.PASSWORD})
        self.assertEqual(response.status_code, 503)
        close.assert_called_once()
        self.assertFalse(response.headers.getlist('Set-Cookie'))
        self.assertTrue(self.client.get('/api/auth/me').json['authenticated'])
