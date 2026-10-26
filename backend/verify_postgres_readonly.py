"""Opt-in real PostgreSQL lifecycle/credential-availability checks; SELECTs only.

Never calls application initialization/login: those may migrate/write auth rows.
No URLs, account identities, passwords, hashes or driver messages are emitted.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import logging
from pathlib import Path
from time import perf_counter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import app
    from database import connect_database, close_database_pools
    from services.database_diagnostics import exception_details
    from werkzeug.security import check_password_hash
    logging.disable(logging.CRITICAL)
    evidence = dict(database='PostgreSQL', mode='read-only; no migrations or application login', sequential=[], concurrent=[])
    if not app.DATABASE_URL:
        evidence['blocked'] = 'PostgreSQL is not configured; SQLite was not opened.'
    else:
        def read(index):
            started = perf_counter()
            c = connect_database(app.DATABASE_URL, 'unused-never-opened.db')
            acquired = perf_counter()
            try:
                encrypted = bool(c._connection.pgconn.ssl_in_use)
                with c:
                    c.execute('SET TRANSACTION READ ONLY')
                    row = c.execute("SELECT 1 AS value, current_setting('transaction_read_only') AS read_only").fetchone()
                    assert row['value'] == 1 and row['read_only'] == 'on'
                assert c._connection.info.transaction_status.name == 'IDLE'
                return dict(index=index, acquisition_ms=round((acquired-started)*1000,2), total_ms=round((perf_counter()-started)*1000,2), encrypted=encrypted, read_only=True)
            finally:
                c.close()

        try:
            for index in range(6): evidence['sequential'].append(read(index+1))
            with ThreadPoolExecutor(max_workers=4) as executor:
                evidence['concurrent'] = list(executor.map(read, range(1,9)))
            c = connect_database(app.DATABASE_URL, 'unused-never-opened.db')
            try:
                try:
                    with c:
                        c.execute('SET TRANSACTION READ ONLY')
                        c.execute('SELECT 1').fetchone()
                        raise RuntimeError('intentional read-only lifecycle rollback')
                except RuntimeError:
                    pass
                evidence['exception_rollback_idle'] = c._connection.info.transaction_status.name == 'IDLE'
                assert evidence['exception_rollback_idle']
            finally:
                c.close()
            evidence['post_exception_read'] = read(1)
            # Only inspect the file specifically authorized by the user. Compare
            # credentials locally only if an exact matching PostgreSQL row exists.
            path = Path(__file__).parent/'instance/verified-demo/credentials.txt'
            found = active = matching = checked = 0
            if path.is_file():
                import re
                credentials = re.findall(r'Email: ([^\r\n]+)\r?\nPassword: ([^\r\n]+)',path.read_text(encoding='utf-8'))
                c = connect_database(app.DATABASE_URL,'unused-never-opened.db')
                try:
                    with c:
                        c.execute('SET TRANSACTION READ ONLY')
                        for email, password in credentials:
                            checked += 1
                            row = c.execute('SELECT is_active,password_hash FROM users WHERE lower(email)=?',(email.strip().lower(),)).fetchone()
                            if row:
                                found += 1
                                active += int(bool(row['is_active']))
                                matching += int(bool(row['is_active']) and check_password_hash(row['password_hash'],password))
                finally:
                    c.close()
            evidence['authorized_file_check'] = dict(file_present=path.is_file(),local_demo_accounts_checked=checked,postgres_accounts_found=found,active_found=active,matching_passwords=matching,identities_and_secrets_emitted=False)
            evidence['login_verification'] = dict(status='blocked',reason='No matching PostgreSQL test account in the authorized local demo file.' if not matching else 'Matching credentials found read-only; normal login writes production auth/rate-limit records and was not attempted under the no-production-mutation constraint.',application_login_attempted=False)
            pool = c._pool
            stats = pool.get_stats()
            evidence['pool_after_release'] = {key:stats.get(key,0) for key in ('pool_size','pool_available','requests_waiting','connections_errors')}
            evidence['all_connections_returned'] = stats.get('pool_size')==stats.get('pool_available') and stats.get('requests_waiting',0)==0
            assert evidence['all_connections_returned']
            evidence['connection_checks_passed'] = True
        except Exception as error:
            evidence['connection_checks_passed'] = False
            evidence['failure'] = exception_details(error)
        finally:
            close_database_pools()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence))
    return 0 if evidence.get('connection_checks_passed') else 1


if __name__=='__main__':
    raise SystemExit(main())
