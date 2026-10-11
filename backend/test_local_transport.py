"""HTTP development does not weaken production transport or CSRF checks."""
import unittest
from unittest.mock import patch
import app
import test_admin_dashboard as fixtures


class LocalTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ManagerTests.setUpClass()

    def setUp(self):
        fixture = fixtures.ManagerTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        self.client = app.app.test_client()

    def test_local_login_refresh_and_logout(self):
        with patch.dict(app.app.config, LOCAL_HTTP_DEVELOPMENT=True):
            response = self.client.post('/api/auth/login', base_url='http://localhost', json={'email': 'manager@example.com', 'password': fixtures.PASSWORD})
            self.assertEqual(response.status_code, 200)
            cookies = response.headers.getlist('Set-Cookie')
            self.assertTrue(any(h.startswith('reqquality_access=') for h in cookies))
            self.assertTrue(any(h.startswith('reqquality_refresh=') for h in cookies))
            self.assertTrue(all('Secure' not in h and 'HttpOnly' in h for h in cookies))
            self.assertTrue(self.client.get('/api/auth/me', base_url='http://localhost').json['authenticated'])
            self.assertEqual(self.client.post('/api/auth/refresh', base_url='http://localhost').status_code, 403)
            response = self.client.post('/api/auth/refresh', base_url='http://localhost', headers={'X-CSRF-Token': response.json['csrf_token']})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.client.post('/api/auth/logout', base_url='http://localhost', headers={'X-CSRF-Token': response.json['csrf_token']}).status_code, 200)
            self.assertFalse(self.client.get('/api/auth/me', base_url='http://localhost').json['authenticated'])
            self.assertEqual(self.client.get('/api/health', base_url='http://evil.example').status_code, 403)

    def test_wsgi_stays_https_only(self):
        self.assertFalse(app.LOCAL_HTTP_DEVELOPMENT)
        for path in ('/api/auth/login', '/api/auth/refresh'):
            self.assertEqual(self.client.post(path, base_url='http://localhost', headers={'X-Forwarded-Proto': 'https'}).status_code, 426)
