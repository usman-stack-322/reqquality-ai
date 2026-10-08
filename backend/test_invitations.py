"""Run: .venv/Scripts/python.exe -m unittest -v test_invitations (from backend)."""
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import app as application
from test_auth_helpers import authenticate
import invitations as inv
from werkzeug.security import generate_password_hash, check_password_hash

PASSWORD = 'correct horse battery staple'


class InvitationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(application, DATABASE_URL=None, DATABASE=Path(self.temp.name) / 'test.db')
        self.settings.start()
        application.app.config.update(TESTING=True, SECRET_KEY='test-only-secret', SESSION_COOKIE_SECURE=False)
        self.sender = patch.object(inv, 'send_invitation')
        self.mail = self.sender.start()
        c = application.get_connection()
        with c:
            for name, role in [('Admin', 'admin'), ('Analyst', 'Analyst'), ('Engineer', 'SQA Engineer')]:
                c.execute('INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,?)', (name, name.lower()+'@example.com', generate_password_hash(PASSWORD), role))
        c.close()
        self.admin = self.client(1)
        self.guest = self.client()

    def tearDown(self):
        self.sender.stop()
        self.settings.stop()
        self.temp.cleanup()

    def client(self, user_id=None):
        client = application.app.test_client()
        if user_id:
            authenticate(client, user_id, csrf='admin-csrf')
        return client

    def create(self, role='Analyst', email='invited@example.com'):
        response = self.admin.post('/api/admin/invitations', json={'name': 'Invited User', 'email': email, 'role': role}, headers={'X-CSRF-Token': 'admin-csrf'})
        self.assertEqual(response.status_code, 201, response.json)
        return response.json['invitation_id'], self.mail.call_args.args[1]

    def row(self, invitation_id):
        c = application.get_connection()
        try:
            return dict(c.execute('SELECT * FROM user_invitations WHERE id = ?', (invitation_id,)).fetchone())
        finally:
            c.close()

    def update(self, invitation_id, **fields):
        c = application.get_connection()
        with c:
            c.execute('UPDATE user_invitations SET '+','.join(key+' = ?' for key in fields)+' WHERE id = ?', (*fields.values(), invitation_id))
        c.close()

    def validate(self, token):
        return self.guest.post('/api/invitations/validate', json={'token': token})

    def verify(self, token, email='invited@example.com', client=None):
        return (client or self.guest).post('/api/invitations/verify-email', json={'token': token, 'email': email})

    def accept(self, token, extra=None, client=None):
        client = client or self.guest
        with client.session_transaction() as session:
            csrf = session.get('invitation_csrf', '')
        return client.post('/api/invitations/accept', json={'token': token, 'password': PASSWORD, **(extra or {})}, headers={'X-CSRF-Token': csrf})

    def test_01_admin_sqa_invitation(self):
        invitation_id, token = self.create('SQA Engineer')
        row = self.row(invitation_id)
        self.assertEqual(row['role'], 'SQA Engineer')
        self.assertEqual(row['token_hash'], inv.digest(token))
        self.assertNotIn(token, str(row))
        self.assertEqual(row['invited_by'], 1)

    def test_02_admin_analyst_invitation(self):
        invitation_id, _ = self.create('Analyst', '  INVITED@Example.com  ')
        self.assertEqual(self.row(invitation_id)['email'], 'invited@example.com')

    def test_03_correct_email_accepts_only_after_registration(self):
        invitation_id, token = self.create('SQA Engineer')
        self.assertEqual(self.validate(token).status_code, 200)
        self.assertEqual(self.verify(token, ' INVITED@EXAMPLE.COM ').status_code, 200)
        self.assertEqual(self.row(invitation_id)['status'], 'pending')
        self.assertEqual(self.accept(token).status_code, 201)
        self.assertEqual(self.row(invitation_id)['status'], 'accepted')
        self.assertIsNotNone(self.row(invitation_id)['accepted_at'])
        c = application.get_connection()
        user = c.execute('SELECT * FROM users WHERE email = ?', ('invited@example.com',)).fetchone()
        c.close()
        self.assertEqual(user['role'], 'SQA Engineer')
        self.assertTrue(check_password_hash(user['password_hash'], PASSWORD))
        self.assertEqual(self.guest.post('/api/auth/login', json={'email': 'INVITED@example.com', 'password': PASSWORD}).status_code, 200)

    def test_04_wrong_email_keeps_pending_and_private(self):
        invitation_id, token = self.create()
        response = self.verify(token, 'wrong@example.com')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error'], 'The provided information does not match this invitation.')
        self.assertNotIn('invited@example.com', str(response.json))
        self.assertEqual(self.row(invitation_id)['status'], 'pending')
        self.assertEqual(self.validate(token).status_code, 200)
        self.assertNotIn('email', self.validate(token).json)

    def test_05_failed_attempt_increments(self):
        invitation_id, token = self.create()
        self.verify(token, 'wrong@example.com')
        row = self.row(invitation_id)
        self.assertEqual(row['failed_attempts'], 1)
        self.assertIsNotNone(row['last_failed_attempt_at'])

    def test_06_correct_after_wrong_succeeds(self):
        _, token = self.create()
        self.verify(token, 'wrong@example.com')
        self.assertEqual(self.verify(token).status_code, 200)
        self.assertEqual(self.accept(token).status_code, 201)

    def test_07_five_failures_lock(self):
        invitation_id, token = self.create()
        for _ in range(4):
            self.assertEqual(self.verify(token, 'wrong@example.com').status_code, 400)
        self.assertEqual(self.verify(token, 'wrong@example.com').status_code, 429)
        self.assertEqual(self.verify(token).status_code, 429)
        self.assertEqual(self.row(invitation_id)['failed_attempts'], 5)

    def test_08_temporary_lock_recovers_without_changing_expiry(self):
        invitation_id, token = self.create()
        expiry = self.row(invitation_id)['expires_at']
        for _ in range(5):
            self.verify(token, 'wrong@example.com')
        self.assertEqual(self.row(invitation_id)['status'], 'pending')
        self.assertEqual(self.row(invitation_id)['expires_at'], expiry)
        with patch.object(inv, 'now', return_value=inv.now()+timedelta(minutes=16)):
            self.assertEqual(self.verify(token).status_code, 200)
            self.assertEqual(self.accept(token).status_code, 201)

    def test_09_expired_rejected_and_marked(self):
        invitation_id, token = self.create()
        self.update(invitation_id, expires_at=inv.stamp(inv.now()-timedelta(seconds=1)))
        self.assertEqual(self.validate(token).status_code, 410)
        self.assertEqual(self.row(invitation_id)['status'], 'expired')
        self.assertEqual(self.verify(token).status_code, 410)

    def test_10_used_rejected(self):
        _, token = self.create()
        self.verify(token)
        self.accept(token)
        self.assertEqual(self.validate(token).json['error'], 'This invitation has already been used.')
        self.assertEqual(self.accept(token).status_code, 410)

    def test_11_revoke_after_verification_stops_acceptance(self):
        invitation_id, token = self.create()
        self.verify(token)
        self.assertEqual(self.admin.post(f'/api/admin/invitations/{invitation_id}/revoke', headers={'X-CSRF-Token':'admin-csrf'}).status_code, 200)
        self.assertEqual(self.validate(token).status_code, 410)
        self.assertEqual(self.accept(token).status_code, 410)
        self.assertIsNotNone(self.row(invitation_id)['revoked_at'])

    def test_12_random_token_rejected(self):
        self.assertEqual(self.validate('x'*43).status_code, 400)
        self.assertEqual(self.validate('').status_code, 400)

    def test_13_unauthenticated_admin_api_denied(self):
        self.assertEqual(self.guest.post('/api/admin/invitations', json={}).status_code, 401)
        self.assertEqual(self.guest.get('/api/admin/invitations').status_code, 401)

    def assert_non_admin(self, user_id):
        client = self.client(user_id)
        for path in ['/api/admin/invitations', '/api/admin/invitations/1']:
            self.assertEqual(client.get(path).status_code, 403)
        for path in ['/api/admin/invitations', '/api/admin/invitations/1/resend', '/api/admin/invitations/1/revoke']:
            self.assertEqual(client.post(path, json={}, headers={'X-CSRF-Token':'admin-csrf'}).status_code, 403)

    def test_14_sqa_admin_access_forbidden(self):
        self.assert_non_admin(3)

    def test_15_analyst_admin_access_forbidden(self):
        self.assert_non_admin(2)

    def test_16_simultaneous_acceptance_only_one_account(self):
        invitation_id, token = self.create()
        clients = [self.client(), self.client()]
        for client in clients:
            self.assertEqual(self.verify(token, client=client).status_code, 200)
        barrier = Barrier(2)
        def attempt(client):
            barrier.wait()
            return self.accept(token, client=client).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, clients))
        self.assertEqual(sorted(results), [201, 410])
        c = application.get_connection()
        self.assertEqual(c.execute("SELECT count(*) FROM users WHERE email = 'invited@example.com'").fetchone()[0], 1)
        c.close()
        self.assertEqual(self.row(invitation_id)['status'], 'accepted')

    def test_17_existing_email_rejected(self):
        response = self.admin.post('/api/admin/invitations', json={'name':'Already Registered', 'email':'ANALYST@example.com', 'role':'Analyst'}, headers={'X-CSRF-Token':'admin-csrf'})
        self.assertEqual(response.status_code, 409)

    def test_18_resend_invalidates_old_link_and_verification(self):
        invitation_id, token = self.create()
        self.verify(token)
        response = self.admin.post(f'/api/admin/invitations/{invitation_id}/resend', headers={'X-CSRF-Token':'admin-csrf'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.validate(token).status_code, 400)
        self.assertEqual(self.accept(token).status_code, 400)
        new_token = self.mail.call_args.args[1]
        self.assertEqual(self.accept(new_token).status_code, 403)

    def test_19_new_link_works_resets_failures(self):
        invitation_id, token = self.create()
        self.verify(token, 'wrong@example.com')
        self.admin.post(f'/api/admin/invitations/{invitation_id}/resend', headers={'X-CSRF-Token':'admin-csrf'})
        new_token = self.mail.call_args.args[1]
        self.assertNotEqual(token, new_token)
        self.assertEqual(self.row(invitation_id)['failed_attempts'], 0)
        self.assertEqual(self.validate(new_token).status_code, 200)
        self.assertEqual(self.verify(new_token).status_code, 200)
        self.assertEqual(self.accept(new_token).status_code, 201)

    def test_20_delivery_failure_recorded_and_retry_works(self):
        self.mail.side_effect = RuntimeError('smtp failure')
        response = self.admin.post('/api/admin/invitations', json={'name':'Invited User','email':'invited@example.com','role':'Analyst'}, headers={'X-CSRF-Token':'admin-csrf'})
        self.assertEqual(response.status_code, 502)
        invitation_id = response.json['invitation_id']
        self.assertEqual(self.row(invitation_id)['delivery_status'], 'failed')
        self.mail.side_effect = None
        self.assertEqual(self.admin.post(f'/api/admin/invitations/{invitation_id}/resend', headers={'X-CSRF-Token':'admin-csrf'}).status_code, 201)
        self.assertEqual(self.row(invitation_id)['delivery_status'], 'sent')

    def test_21_exact_24_hours_and_boundary(self):
        fixed = inv.now()
        with patch.object(inv, 'now', return_value=fixed):
            invitation_id, token = self.create()
        row = self.row(invitation_id)
        self.assertEqual(inv.datetime.fromisoformat(row['expires_at'])-inv.datetime.fromisoformat(row['created_at']), timedelta(hours=24))
        with patch.object(inv, 'now', return_value=fixed+timedelta(hours=24)-timedelta(microseconds=1)):
            self.assertEqual(self.validate(token).status_code, 200)
        with patch.object(inv, 'now', return_value=fixed+timedelta(hours=24)):
            self.assertEqual(self.validate(token).status_code, 410)

    def test_22_role_tampering_rejected(self):
        _, token = self.create()
        self.verify(token)
        self.assertEqual(self.accept(token, {'role':'admin'}).status_code, 400)
        self.assertEqual(self.accept(token).status_code, 201)

    def test_23_email_tampering_rejected(self):
        _, token = self.create()
        self.verify(token)
        self.assertEqual(self.accept(token, {'email':'replacement@example.com'}).status_code, 400)
        self.assertEqual(self.accept(token).status_code, 201)

    def test_24_validation_and_csrf(self):
        for payload in [{}, {'name':'a','email':'x@example.com','role':'Analyst'}, {'name':'Valid Name','email':'bad','role':'Analyst'}, {'name':'Valid Name','email':'x@example.com','role':'admin'}]:
            self.assertEqual(self.admin.post('/api/admin/invitations', json=payload, headers={'X-CSRF-Token':'admin-csrf'}).status_code, 400)
        self.assertEqual(self.admin.post('/api/admin/invitations', json={}).status_code, 403)
        _, token = self.create()
        self.assertEqual(self.accept(token).status_code, 403)
        self.verify(token)
        self.assertEqual(self.accept(token, {'password':'short'}).status_code, 400)
        self.assertEqual(self.guest.post('/api/auth/register', json={'role':'admin'}).status_code, 403)

    def test_25_duplicate_pending_and_admin_view_privacy(self):
        invitation_id, token = self.create()
        response = self.admin.post('/api/admin/invitations', json={'name':'Other Name','email':'INVITED@example.com','role':'Analyst'}, headers={'X-CSRF-Token':'admin-csrf'})
        self.assertEqual(response.status_code, 409)
        response = self.admin.get(f'/api/admin/invitations/{invitation_id}')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('token_hash', response.json['invitation'])
        self.assertNotIn(token, str(response.json))
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_26_expiry_between_verify_and_accept(self):
        invitation_id, token = self.create()
        self.verify(token)
        self.update(invitation_id, expires_at=inv.stamp(inv.now()))
        self.assertEqual(self.accept(token).status_code, 410)

    def test_27_smtp_message_and_secure_transport(self):
        with patch.dict(os.environ, {'INVITATION_FRONTEND_URL':'https://app.example.com','SMTP_HOST':'smtp.example.com','SMTP_FROM':'admin@example.com','SMTP_USERNAME':'sender','SMTP_PASSWORD':'test-secret','SMTP_SSL':'false'}), patch.object(inv.smtplib, 'SMTP') as transport:
            smtp = transport.return_value.__enter__.return_value
            smtp.send_message.return_value = {}
            self.sender.stop()
            try:
                inv.send_invitation({'name':'Invited Name','email':'exact@example.com','role':'SQA Engineer'}, 'test-token')
            finally:
                self.mail = self.sender.start()
            smtp.starttls.assert_called_once()
            smtp.login.assert_called_once_with('sender','test-secret')
            message = smtp.send_message.call_args.args[0]
            self.assertEqual(message['To'], 'exact@example.com')
            for text in ['Invited Name','SQA Engineer','ReqQuality AI','24 hours','once','https://app.example.com/accept-invitation?token=test-token']:
                self.assertIn(text, message.get_content())

    def test_28_legacy_sqlite_migration_retains_foreign_keys(self):
        path = Path(self.temp.name) / 'legacy.db'
        c = sqlite3.connect(path)
        c.executescript("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('Analyst','SQA Reviewer')), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP); INSERT INTO users(name,email,password_hash,role) VALUES ('Legacy','legacy@example.com','hash','SQA Reviewer'); CREATE TABLE references_user (user_id INTEGER REFERENCES users(id)); INSERT INTO references_user VALUES (1);")
        c.close()
        with patch.object(application, 'DATABASE', path):
            c = application.get_connection()
            self.assertEqual(c.execute('SELECT role FROM users WHERE id = 1').fetchone()[0], 'SQA Engineer')
            self.assertEqual(c.execute('SELECT user_id FROM references_user').fetchone()[0], 1)
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(), [])
            c.close()

    def test_29_existing_session_cleared_on_registration(self):
        _, token = self.create()
        signed_in = self.client(2)
        self.assertEqual(self.verify(token, client=signed_in).status_code, 200)
        self.assertEqual(self.accept(token, client=signed_in).status_code, 201)
        self.assertFalse(signed_in.get('/api/auth/me').json['authenticated'])


if __name__ == '__main__':
    unittest.main()
