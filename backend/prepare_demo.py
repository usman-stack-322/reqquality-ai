"""Provision an explicitly invoked, isolated local demo; never use cloud data."""
import argparse
import json
import os
from pathlib import Path
import secrets


DEFAULT_DIRECTORY = Path(__file__).resolve().parent / 'instance' / 'verified-demo'


def configure(directory):
    settings = json.loads((directory / 'local-config.json').read_text(encoding='utf-8'))
    if settings.get('purpose') != 'reqquality-isolated-demo-v1':
        raise ValueError('Expected an isolated ReqQuality demo configuration.')
    os.environ.update(DATABASE_URL='', SQLITE_DATABASE_PATH=str(directory / 'demo.db'),
                      REQQUALITY_SECRET_KEY=settings['session_secret'], JWT_SECRET_KEY=settings['jwt_secret'],
                      FRONTEND_ORIGINS='http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174',
                      SMTP_HOST='', SMTP_FROM='')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    directory = args.directory.resolve()
    config = directory / 'local-config.json'
    if not config.exists():
        if directory.exists() and any(directory.iterdir()):
            raise SystemExit('Refusing to provision a nonempty directory without a demo marker.')
        directory.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps(dict(purpose='reqquality-isolated-demo-v1',
                                         session_secret=secrets.token_urlsafe(48), jwt_secret=secrets.token_urlsafe(48))), encoding='utf-8')
    configure(directory)
    # Import only after overriding inherited/shared dotenv values explicitly.
    import app
    from seed_demo import seed
    from werkzeug.security import generate_password_hash
    c = app.get_connection()
    credentials = []
    try:
        with c:
            for label, role in (('admin', 'admin'), ('analyst', 'Analyst'), ('engineer', 'SQA Engineer')):
                email = label + '@demo.invalid'
                if c.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone():
                    continue
                password = secrets.token_urlsafe(18)
                c.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',
                          ('[DEMO] ' + role, email, generate_password_hash(password, method='scrypt'), role))
                credentials.append(f'{role}\nEmail: {email}\nPassword: {password}\n')
        if credentials:
            with (directory / 'credentials.txt').open('a', encoding='utf-8') as output:
                output.write('\n'.join(credentials))
        owner = c.execute("SELECT id FROM users WHERE email='analyst@demo.invalid'").fetchone()[0]
        reviewer = c.execute("SELECT id FROM users WHERE email='engineer@demo.invalid'").fetchone()[0]
        result = seed(c, owner, reviewer)
        print(json.dumps(dict(database=str(directory / 'demo.db'), credentials_file=str(directory / 'credentials.txt'), **result)))
    finally:
        c.close()


if __name__ == '__main__':
    main()
