"""Read-only PostgreSQL diagnosis. Never output credentials or driver messages."""
import json
import os
import socket
import ssl
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict
from dotenv import dotenv_values, load_dotenv


def report(stage, **details):
    print(json.dumps({'stage': stage, **details}), flush=True)


def main():
    directory = Path(__file__).resolve().parent
    inherited = bool(os.environ.get('DATABASE_URL'))
    backend_values = dotenv_values(directory / '.env')
    root_values = dotenv_values(directory.parent / '.env')
    load_dotenv(directory / '.env')
    load_dotenv(directory.parent / '.env')
    url = os.environ.get('DATABASE_URL')
    source = 'process environment' if inherited else 'backend/.env' if backend_values.get('DATABASE_URL') else 'root .env'
    report('environment', database_configured=bool(url), source=source,
           conflicting_files=bool(backend_values.get('DATABASE_URL') and root_values.get('DATABASE_URL') and backend_values['DATABASE_URL'] != root_values['DATABASE_URL']),
           secrets_long_enough=all(len(os.environ.get(k, '').encode()) >= 32 for k in ('REQQUALITY_SECRET_KEY', 'JWT_SECRET_KEY')),
           pool_wait_seconds=os.environ.get('DB_POOL_TIMEOUT', '10'))
    if not url:
        report('configuration', result='PostgreSQL not configured')
        return 1
    url = url.strip().replace('postgresql+psycopg://', 'postgresql://', 1)
    try:
        config = conninfo_to_dict(url)
        host = config['host']
        port = int(config.get('port', 5432))
        report('configuration', parsed=True, port=port, sslmode=config.get('sslmode', 'prefer'),
               pooled_endpoint='-pooler.' in host, driver_connect_timeout_seconds=10)
        addresses = sorted({row[4][0] for row in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
    except Exception as error:
        report('configuration_or_dns', result=type(error).__name__)
        return 1
    report('dns', resolved=True, address_count=len(addresses))

    def probe(item):
        index, address = item
        started = time.perf_counter()
        try:
            with socket.create_connection((address, port), timeout=3) as sock:
                tcp_ms = round((time.perf_counter() - started) * 1000)
                # Standard PostgreSQL SSLRequest; no credentials are sent.
                sock.sendall(struct.pack('!II', 8, 80877103))
                if sock.recv(1) != b'S':
                    return {'address_index': index, 'tcp': 'connected', 'tcp_ms': tcp_ms, 'tls': 'not accepted'}
                context = ssl.create_default_context()
                with context.wrap_socket(sock, server_hostname=host) as secure:
                    return {'address_index': index, 'tcp': 'connected', 'tcp_ms': tcp_ms, 'tls': 'certificate and hostname verified', 'tls_version': secure.version()}
        except Exception as error:
            return {'address_index': index, 'result': type(error).__name__, 'elapsed_ms': round((time.perf_counter() - started) * 1000)}

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(probe, enumerate(addresses)))
    report('tcp_tls', results=results)
    # Never invoke application get_connection: it can perform schema migrations.
    started = time.perf_counter()
    try:
        with psycopg.connect(url, connect_timeout=3, options='-c default_transaction_read_only=on') as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1, current_setting(\'transaction_read_only\')')
                value, read_only = cursor.fetchone()
                report('read_only_query', successful=value == 1, transaction_read_only=read_only,
                       elapsed_ms=round((time.perf_counter() - started) * 1000))
                cursor.execute("SELECT count(*), count(*) FILTER (WHERE is_active=1) FROM users WHERE role='admin'")
                count, active = cursor.fetchone()
                report('admin', present=count > 0, active_admin_present=active > 0, total_admins=count, active_admins=active)
        return 0
    except Exception as error:
        # Driver messages may contain credentials; classify without emitting them.
        message = str(error).lower()
        report('read_only_query', successful=False, exception_type=type(error).__name__,
               timeout='timeout' in message, credential_rejected='password authentication failed' in message,
               elapsed_ms=round((time.perf_counter() - started) * 1000))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
