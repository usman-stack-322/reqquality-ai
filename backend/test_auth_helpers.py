"""HTTPS and cookie-token fixtures; no production session-authentication fallback."""
import jwt
from flask.testing import FlaskClient
import app
from services.token_service import issue_tokens, ACCESS_COOKIE, REFRESH_COOKIE


class SecureTestClient(FlaskClient):
    def open(self, *args, **kwargs):
        kwargs.setdefault('base_url', 'https://localhost')
        return super().open(*args, **kwargs)


app.app.test_client_class = SecureTestClient


def authenticate(client, user_id, csrf='test-csrf', auth_version=0):
    connection = app.get_connection()
    try:
        user = dict(connection.execute('SELECT id,name,email,role,created_at,is_active,auth_version FROM users WHERE id=?', (user_id,)).fetchone())
        user['auth_version'] = auth_version
        with app.app.test_request_context(base_url='https://localhost'):
            from flask import g
            with connection:
                issue_tokens(user, connection)
            values = g.auth_cookies
            claims = jwt.decode(values['access'], options={'verify_signature': False})
            claims['csrf'] = csrf
            access = jwt.encode(claims, app.app.config['JWT_SECRET_KEY'], algorithm='HS256')
            client.set_cookie(ACCESS_COOKIE, access, domain='localhost', path='/api/', secure=True, httponly=True)
            client.set_cookie(REFRESH_COOKIE, values['refresh'], domain='localhost', path='/api/auth/', secure=True, httponly=True)
    finally:
        connection.close()
