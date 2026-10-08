"""Email-based, single-use password recovery."""
import os
import secrets
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from urllib.parse import urlsplit
from flask import g, session
from werkzeug.security import generate_password_hash
from invitations import EMAIL, digest, now, stamp
from database import DATABASE_ERRORS

def send_reset_email(email, token):
    base = os.getenv('PASSWORD_RESET_FRONTEND_URL') or os.getenv('INVITATION_FRONTEND_URL', '')
    base = base.rstrip('/')
    parsed = urlsplit(base)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError('Invalid frontend URL configuration')
    message = EmailMessage()
    message['Subject'] = 'Reset your ReqQuality AI password'
    message['From'] = os.environ['SMTP_FROM']
    message['To'] = email
    message.set_content(f'Open {base}/#reset-password?token={token}\n\nThis link expires in one hour and can only be used once.\nIf you did not request this, you can ignore this email.\n')
    use_ssl = os.getenv('SMTP_SSL', 'false').lower() == 'true'
    transport = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    options = {'timeout': 15}
    if use_ssl:
        options['context'] = ssl.create_default_context()
    with transport(os.environ['SMTP_HOST'], int(os.getenv('SMTP_PORT', '465' if use_ssl else '587')), **options) as smtp:
        if not use_ssl:
            smtp.starttls(context=ssl.create_default_context())
        if os.getenv('SMTP_USERNAME'):
            smtp.login(os.environ['SMTP_USERNAME'], os.environ['SMTP_PASSWORD'])
        if smtp.send_message(message):
            raise RuntimeError('Recipient refused')
from types import SimpleNamespace
from services.responses import response_payload

def create_services(app, get_connection):

    def connect():
        connection = get_connection()
        connection.execute('CREATE TABLE IF NOT EXISTS password_resets (\n            user_id BIGINT PRIMARY KEY REFERENCES users(id), token_hash TEXT NOT NULL UNIQUE,\n            created_at TEXT NOT NULL, expires_at TEXT NOT NULL, auth_version INTEGER NOT NULL)')
        connection.commit()
        return connection

    def forgot_password(payload):
        data = payload
        email = data.get('email') if isinstance(data, dict) else None
        if not isinstance(email, str) or len(email.strip()) > 254 or (not EMAIL.fullmatch(email.strip())):
            return (response_payload(error='Enter a valid email address.'), 400)
        connection = connect()
        try:
            user = connection.execute('SELECT id,email,auth_version FROM users WHERE lower(email)=? AND is_active=1', (email.strip().lower(),)).fetchone()
            if user:
                token, current = (secrets.token_urlsafe(32), now())
                with connection:
                    cursor = connection.execute('INSERT INTO password_resets (user_id,token_hash,created_at,expires_at,auth_version)\n                        VALUES (?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET\n                        token_hash=excluded.token_hash,created_at=excluded.created_at,\n                        expires_at=excluded.expires_at,auth_version=excluded.auth_version\n                        WHERE password_resets.created_at < ?', (user['id'], digest(token), stamp(current), stamp(current + timedelta(hours=1)), user['auth_version'], stamp(current - timedelta(minutes=5))))
                if cursor.rowcount:
                    try:
                        send_reset_email(user['email'], token)
                    except Exception:
                        app.logger.error('Password reset email delivery failed')
                        with connection:
                            connection.execute('DELETE FROM password_resets WHERE token_hash=?', (digest(token),))
            return response_payload(message='If an active account exists for this email, a password reset link will be sent. Check your inbox and spam folder.')
        except DATABASE_ERRORS:
            app.logger.error('Password reset database operation failed')
            return (response_payload(error='Unable to request a reset. Please try again.'), 503)
        finally:
            connection.close()

    def reset_password(payload):
        data = payload
        token = data.get('token') if isinstance(data, dict) else None
        password = data.get('password') if isinstance(data, dict) else None
        if not isinstance(token, str) or not 20 <= len(token) <= 128:
            return (response_payload(error='This reset link is invalid or expired. Request a new link.'), 400)
        if not isinstance(password, str) or not 12 <= len(password) <= 128:
            return (response_payload(error='Password must be between 12 and 128 characters.'), 400)
        password_hash = generate_password_hash(password, method='scrypt')
        connection = connect()
        try:
            with connection:
                cursor = connection.execute('UPDATE users SET password_hash=?,auth_version=auth_version+1\n                    WHERE is_active=1 AND id IN (SELECT user_id FROM password_resets\n                    WHERE token_hash=? AND expires_at>? AND auth_version=users.auth_version)', (password_hash, digest(token), stamp(now())))
                if not cursor.rowcount:
                    return (response_payload(error='This reset link is invalid or expired. Request a new link.'), 400)
                from services.token_service import revoke_user_tokens
                # The reset above increments auth_version; revoke that account's stored refresh credentials.
                connection.execute('UPDATE auth_refresh_tokens SET revoked_at=? WHERE user_id IN (SELECT user_id FROM password_resets WHERE token_hash=?) AND revoked_at IS NULL', (int(now().timestamp()), digest(token)))
                connection.execute('DELETE FROM password_resets WHERE token_hash=?', (digest(token),))
            g.clear_auth_cookies = True
            session.clear()
            return response_payload(message='Password reset successfully. Sign in with your new password.')
        except DATABASE_ERRORS:
            return (response_payload(error='Unable to reset your password. Please try again.'), 503)
        finally:
            connection.close()
    return SimpleNamespace(forgot_password=forgot_password, reset_password=reset_password)
