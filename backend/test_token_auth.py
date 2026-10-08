"""Cookie-token authentication: isolated databases, actual JWT signatures and hashing."""
import hashlib
import time
import unittest
from http.cookies import SimpleCookie
import jwt
import app
import test_admin_dashboard as fixtures
from services.token_service import ACCESS_COOKIE, REFRESH_COOKIE, AUDIENCE, ISSUER


class TokenAuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ManagerTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.ManagerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.client = app.app.test_client()

    def login(self, client=None):
        response = (client or self.client).post('/api/auth/login', json={'email': 'manager@example.com', 'password': fixtures.PASSWORD})
        self.assertEqual(response.status_code, 200)
        return response

    def access(self, client=None):
        return (client or self.client).get_cookie(ACCESS_COOKIE, path='/api/').value

    def refresh(self, client=None):
        return (client or self.client).get_cookie(REFRESH_COOKIE, path='/api/auth/').value

    def claims(self, encoded=None):
        return jwt.decode(encoded or self.access(), app.app.config['JWT_SECRET_KEY'], algorithms=['HS256'], issuer=ISSUER, audience=AUDIENCE)

    def install(self, client, access=None, refresh=None):
        if access:
            client.set_cookie(ACCESS_COOKIE, access, path='/api/', secure=True, httponly=True)
        if refresh:
            client.set_cookie(REFRESH_COOKIE, refresh, path='/api/auth/', secure=True, httponly=True)

    def expire_access(self):
        claims = self.claims()
        claims['exp'] = int(time.time()) - 1
        self.install(self.client, access=jwt.encode(claims, app.app.config['JWT_SECRET_KEY'], algorithm='HS256'))

    def test_login_issues_secure_httponly_cookies_and_only_refresh_hash_is_persisted(self):
        response = self.login()
        self.assertNotIn('access_token', response.json)
        self.assertNotIn('refresh_token', response.json)
        claims = self.claims()
        self.assertEqual(claims['exp'] - claims['iat'], 3600)
        cookies = SimpleCookie()
        for header in response.headers.getlist('Set-Cookie'):
            cookies.load(header)
        for name, duration in [(ACCESS_COOKIE, 3600), (REFRESH_COOKIE, 86400)]:
            self.assertTrue(cookies[name]['secure'])
            self.assertTrue(cookies[name]['httponly'])
            self.assertEqual(cookies[name]['samesite'], 'Lax')
            self.assertGreaterEqual(int(cookies[name]['max-age']), duration - 2)
        rows = self.fixture.sql('SELECT * FROM auth_refresh_tokens WHERE token_hash=?', (hashlib.sha256(self.refresh().encode()).hexdigest(),))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['expires_at'] - rows[0]['created_at'], 86400)
        self.assertNotIn(self.refresh(), str(rows))
        with self.client.session_transaction() as session:
            self.assertNotIn('user_id', session)

    def test_plain_http_login_is_rejected(self):
        response = self.client.post('/api/auth/login', base_url='http://localhost', json={'email': 'manager@example.com', 'password': fixtures.PASSWORD})
        self.assertEqual(response.status_code, 426)
        self.assertFalse(any(ACCESS_COOKIE in h for h in response.headers.getlist('Set-Cookie')))

    def test_session_cookie_cannot_authenticate(self):
        with self.client.session_transaction() as session:
            session.update(user_id=1, csrf_token='fake', auth_version=0)
        self.assertEqual(self.client.get('/api/admin/dashboard').status_code, 401)

    def test_csrf_bootstrap_and_logout_protection(self):
        response = self.login()
        self.assertEqual(self.client.get('/api/auth/csrf').json['csrf_token'], response.json['csrf_token'])
        self.assertEqual(self.client.post('/api/auth/logout').status_code, 403)
        self.assertEqual(self.client.get('/api/admin/dashboard').status_code, 200)
        self.assertEqual(self.client.post('/api/auth/logout', headers={'X-CSRF-Token': response.json['csrf_token']}).status_code, 200)
        self.assertIsNone(self.client.get_cookie(ACCESS_COOKIE, path='/api/'))
        self.assertIsNone(self.client.get_cookie(REFRESH_COOKIE, path='/api/auth/'))

    def test_refresh_rotates_both_cookies_and_keeps_original_24_hour_deadline(self):
        login = self.login()
        old_access, old_refresh = self.access(), self.refresh()
        old_rows = self.fixture.sql('SELECT expires_at FROM auth_refresh_tokens WHERE token_hash=?', (hashlib.sha256(old_refresh.encode()).hexdigest(),))
        self.expire_access()
        self.assertEqual(self.client.get('/api/admin/dashboard').status_code, 401)
        csrf = self.client.get('/api/auth/csrf').json['csrf_token']
        response = self.client.post('/api/auth/refresh', headers={'X-CSRF-Token': csrf})
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(self.access(), old_access)
        self.assertNotEqual(self.refresh(), old_refresh)
        self.assertNotEqual(response.json['csrf_token'], login.json['csrf_token'])
        self.assertEqual(self.client.get('/api/admin/dashboard').status_code, 200)
        rows = self.fixture.sql('SELECT * FROM auth_refresh_tokens WHERE token_hash=?', (hashlib.sha256(self.refresh().encode()).hexdigest(),))
        self.assertEqual(rows[0]['expires_at'], old_rows[0]['expires_at'])

    def test_refresh_replay_revokes_the_entire_family(self):
        login = self.login()
        old_refresh = self.refresh()
        response = self.client.post('/api/auth/refresh', headers={'X-CSRF-Token': login.json['csrf_token']})
        self.assertEqual(response.status_code, 200)
        attacker = app.app.test_client()
        self.install(attacker, refresh=old_refresh)
        replay = attacker.post('/api/auth/refresh', headers={'X-CSRF-Token': login.json['csrf_token']})
        self.assertEqual(replay.status_code, 401)
        self.assertEqual(self.client.get('/api/admin/dashboard').status_code, 401)

    def test_expired_refresh_is_rejected(self):
        login = self.login()
        self.fixture.sql('UPDATE auth_refresh_tokens SET expires_at=?', (int(time.time()) - 1,))
        self.assertEqual(self.client.post('/api/auth/refresh', headers={'X-CSRF-Token': login.json['csrf_token']}).status_code, 401)

    def test_logout_revokes_copied_access_and_refresh_tokens(self):
        login = self.login()
        copy = app.app.test_client()
        self.install(copy, access=self.access(), refresh=self.refresh())
        self.assertEqual(self.client.post('/api/auth/logout', headers={'X-CSRF-Token': login.json['csrf_token']}).status_code, 200)
        self.assertEqual(copy.get('/api/admin/dashboard').status_code, 401)
        self.assertEqual(copy.post('/api/auth/refresh', headers={'X-CSRF-Token': login.json['csrf_token']}).status_code, 401)

    def test_expired_access_can_still_log_out_using_refresh_cookie(self):
        login = self.login()
        self.expire_access()
        self.assertEqual(self.client.post('/api/auth/logout', headers={'X-CSRF-Token': login.json['csrf_token']}).status_code, 200)

    def test_refresh_needs_csrf_and_rejects_an_access_token_in_refresh_cookie(self):
        login = self.login()
        self.assertEqual(self.client.post('/api/auth/refresh').status_code, 403)
        self.install(self.client, refresh=self.access())
        self.assertEqual(self.client.post('/api/auth/refresh', headers={'X-CSRF-Token': login.json['csrf_token']}).status_code, 401)

    def test_password_change_revokes_all_refresh_credentials(self):
        login = self.login()
        response = self.client.post('/api/auth/change-password', json={'current_password': fixtures.PASSWORD, 'new_password': 'another-password-123'}, headers={'X-CSRF-Token': login.json['csrf_token']})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.fixture.sql('SELECT token_hash FROM auth_refresh_tokens WHERE user_id=1 AND revoked_at IS NULL'))
        self.assertIsNone(self.client.get_cookie(ACCESS_COOKIE, path='/api/'))

    def test_concurrent_refresh_cannot_issue_two_active_successors(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        login = self.login()
        token = self.refresh()
        family_id = self.claims()['sid']
        barrier = Barrier(2)
        def attempt():
            client = app.app.test_client()
            self.install(client, refresh=token)
            barrier.wait(timeout=10)
            return client.post('/api/auth/refresh', headers={'X-CSRF-Token': login.json['csrf_token']}).status_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: attempt(), range(2)))
        self.assertEqual(sorted(results), [200, 401])
        self.assertFalse(self.fixture.sql('SELECT token_hash FROM auth_refresh_tokens WHERE revoked_at IS NULL AND family_id=?', (family_id,)))

    def test_failed_refresh_write_rolls_back_without_setting_replacement_cookies(self):
        from unittest.mock import patch
        login = self.login()
        with patch('services.token_service.issue_tokens', side_effect=RuntimeError('simulated write failure')):
            response = self.client.post('/api/auth/refresh', headers={'X-CSRF-Token': login.json['csrf_token']})
        self.assertEqual(response.status_code, 500)
        self.assertFalse(any(ACCESS_COOKIE in value for value in response.headers.getlist('Set-Cookie')))
        self.assertEqual(self.client.get('/api/admin/dashboard').status_code, 200)

    def test_tampered_access_token_is_rejected(self):
        self.login()
        claims = self.claims()
        claims['sub'] = '2'
        encoded = jwt.encode(claims, 'wrong-signing-key-for-this-test-12345', algorithm='HS256')
        self.install(self.client, access=encoded)
        self.assertEqual(self.client.get('/api/admin/dashboard').status_code, 401)


if __name__ == '__main__':
    unittest.main()
