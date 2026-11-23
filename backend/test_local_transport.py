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

    def test_hosted_origins_cors_and_origin_validation(self):
        for origin in ('https://www.reqqualityai.site', 'https://reqqualityai.site'):
            preflight = self.client.options(
                '/api/auth/login',
                base_url='https://localhost',
                headers={'Origin': origin, 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'Content-Type, X-CSRF-Token'},
            )
            self.assertEqual(preflight.status_code, 200, origin)
            self.assertEqual(preflight.headers.get('Access-Control-Allow-Origin'), origin)
            self.assertEqual(preflight.headers.get('Access-Control-Allow-Credentials'), 'true')

            login = self.client.post(
                '/api/auth/login',
                base_url='https://localhost',
                headers={'Origin': origin},
                json={'email': 'manager@example.com', 'password': fixtures.PASSWORD},
            )
            self.assertEqual(login.status_code, 200, origin)
            self.assertEqual(login.headers.get('Access-Control-Allow-Origin'), origin)
            self.assertEqual(login.headers.get('Access-Control-Allow-Credentials'), 'true')

        rejected = self.client.post(
            '/api/auth/login',
            base_url='https://localhost',
            headers={'Origin': 'https://evil.example'},
            json={'email': 'manager@example.com', 'password': fixtures.PASSWORD},
        )
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(rejected.json['error'], 'Request origin is not allowed.')

    def test_cookie_samesite_none_for_https_and_clamps_to_lax_on_local_http(self):
        with patch.dict(app.app.config, SESSION_COOKIE_SAMESITE='None', SESSION_COOKIE_SECURE=True, LOCAL_HTTP_DEVELOPMENT=False):
            login = self.client.post('/api/auth/login', base_url='https://localhost', json={'email': 'manager@example.com', 'password': fixtures.PASSWORD})
            self.assertEqual(login.status_code, 200)
            cookies = [h for h in login.headers.getlist('Set-Cookie') if 'reqquality_' in h]
            self.assertEqual(len(cookies), 2, cookies)
            self.assertTrue(all('SameSite=None' in h and 'Secure' in h and 'HttpOnly' in h for h in cookies), cookies)

            logout = self.client.post('/api/auth/logout', base_url='https://localhost', headers={'X-CSRF-Token': login.json['csrf_token']})
            self.assertEqual(logout.status_code, 200)
            cleared = [h for h in logout.headers.getlist('Set-Cookie') if 'reqquality_' in h]
            self.assertEqual(len(cleared), 2)
            self.assertTrue(all('SameSite=None' in h and 'Secure' in h and 'HttpOnly' in h for h in cleared), cleared)

        with patch.dict(app.app.config, SESSION_COOKIE_SAMESITE='None', SESSION_COOKIE_SECURE=False, LOCAL_HTTP_DEVELOPMENT=True):
            login = self.client.post('/api/auth/login', base_url='http://localhost', json={'email': 'manager@example.com', 'password': fixtures.PASSWORD})
            self.assertEqual(login.status_code, 200)
            cookies = [h for h in login.headers.getlist('Set-Cookie') if 'reqquality_' in h]
            self.assertEqual(len(cookies), 2, cookies)
            self.assertTrue(all('SameSite=Lax' in h and 'Secure' not in h and 'HttpOnly' in h for h in cookies), cookies)
