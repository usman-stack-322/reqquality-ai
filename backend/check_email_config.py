"""Validate email settings; --connect checks SMTP login without sending email."""

import argparse
import os
import smtplib
import ssl
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connect', action='store_true', help='Check TLS and SMTP authentication.')
    args = parser.parse_args()
    backend = Path(__file__).resolve().parent
    load_dotenv(backend / '.env')
    load_dotenv(backend.parent / '.env')

    required = ['INVITATION_FRONTEND_URL', 'SMTP_HOST', 'SMTP_FROM']
    if os.getenv('SMTP_USERNAME'):
        required.append('SMTP_PASSWORD')
    missing = [key for key in required if not os.getenv(key, '').strip()]
    if missing:
        print('Missing configuration: ' + ', '.join(missing))
        print('Add these values to backend/.env, then run this command again.')
        return 1

    url = urlsplit(os.environ['INVITATION_FRONTEND_URL'])
    if url.scheme not in {'http', 'https'} or not url.netloc or url.query or url.fragment:
        print('INVITATION_FRONTEND_URL must be the frontend base URL, without a query or fragment.')
        return 1
    use_ssl = os.getenv('SMTP_SSL', 'false').lower() == 'true'
    try:
        port = int(os.getenv('SMTP_PORT', '465' if use_ssl else '587'))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        print('SMTP_PORT must be a valid port number.')
        return 1
    print('Required email settings are present; values and credentials are hidden.')
    if url.hostname in {'localhost', '127.0.0.1', '::1'}:
        print('Invitation links use localhost and work only on the computer running the frontend.')
    if not args.connect:
        print('Run with --connect to check TLS and authentication without sending an email.')
        return 0

    transport = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    options = {'timeout': 15}
    if use_ssl:
        options['context'] = ssl.create_default_context()
    try:
        with transport(os.environ['SMTP_HOST'], port, **options) as smtp:
            if not use_ssl:
                smtp.starttls(context=ssl.create_default_context())
            if os.getenv('SMTP_USERNAME'):
                smtp.login(os.environ['SMTP_USERNAME'], os.environ['SMTP_PASSWORD'])
    except smtplib.SMTPAuthenticationError:
        print('SMTP authentication failed. Check the SMTP username and provider-issued password.')
        return 1
    except (OSError, smtplib.SMTPException, ValueError):
        print('SMTP connection failed. Check host, port, TLS mode, and network access.')
        return 1
    print('SMTP connection and configured authentication succeeded. No email was sent.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
