"""Initialize the isolated SQLite development account; never connect to cloud."""
import os
import secrets
from pathlib import Path

from dotenv import dotenv_values
from werkzeug.security import generate_password_hash


def main():
    directory = Path(__file__).resolve().parent
    values = dotenv_values(directory / '.env.local')
    if values.get('DATABASE_URL') != '' or values.get('SQLITE_DATABASE_PATH') != 'instance/local-development.db':
        raise SystemExit('Expected isolated local configuration in backend/.env.local.')
    os.environ.update({key: value for key, value in values.items() if value is not None})
    import app
    if app.DATABASE_URL:
        raise SystemExit('Refusing to provision a cloud account.')
    connection = app.get_connection()
    try:
        email = 'admin@localhost.test'
        if connection.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone():
            print('Local admin already exists; existing credentials preserved.')
            return
        password = secrets.token_urlsafe(18)
        with connection:
            connection.execute(
                "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'admin')",
                ('Local Admin', email, generate_password_hash(password, method='scrypt')),
            )
        credentials = directory / 'instance' / 'local-login.txt'
        credentials.write_text(f'Local development only\nURL: http://127.0.0.1:5173\nEmail: {email}\nPassword: {password}\n', encoding='utf-8')
        print('Local database initialized. Credentials: backend/instance/local-login.txt')
    finally:
        connection.close()


if __name__ == '__main__':
    main()
