import unittest
from unittest.mock import patch

import app as application
import password_reset as recovery
from test_invitations import InvitationTests, PASSWORD


class PasswordResetTests(unittest.TestCase):
    setUp = InvitationTests.setUp
    tearDown = InvitationTests.tearDown
    client = InvitationTests.client
    def test_reset_lifecycle(self):
        with patch.object(recovery, 'send_reset_email') as mail:
            response = self.guest.post('/api/auth/forgot-password', json={'email': 'ANALYST@example.com'})
            self.assertEqual(response.status_code, 200)
            token = mail.call_args.args[1]
            unknown = self.guest.post('/api/auth/forgot-password', json={'email': 'unknown@example.com'})
            self.assertEqual(response.json, unknown.json)
            self.guest.post('/api/auth/forgot-password', json={'email': 'analyst@example.com'})
            self.assertEqual(mail.call_count, 1)
        signed_in = application.app.test_client()
        self.assertEqual(signed_in.post('/api/auth/login', json={'email': 'analyst@example.com', 'password': PASSWORD}).status_code, 200)
        payload = {'token': token, 'password': 'a new secure password'}
        self.assertEqual(self.guest.post('/api/auth/reset-password', json={**payload, 'password': 'short'}).status_code, 400)
        self.assertEqual(self.guest.post('/api/auth/reset-password', json=payload).status_code, 200)
        self.assertFalse(signed_in.get('/api/auth/me').json['authenticated'])
        self.assertEqual(self.guest.post('/api/auth/reset-password', json=payload).status_code, 400)
        self.assertEqual(self.guest.post('/api/auth/login', json={'email': 'analyst@example.com', 'password': PASSWORD}).status_code, 401)
        self.assertEqual(self.guest.post('/api/auth/login', json={'email': 'analyst@example.com', 'password': payload['password']}).status_code, 200)

    def test_expired_link(self):
        with patch.object(recovery, 'send_reset_email') as mail:
            self.guest.post('/api/auth/forgot-password', json={'email': 'analyst@example.com'})
            token = mail.call_args.args[1]
        c = application.get_connection()
        with c:
            c.execute("UPDATE password_resets SET expires_at='2000-01-01'")
        c.close()
        self.assertEqual(self.guest.post('/api/auth/reset-password', json={'token': token, 'password': PASSWORD}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
