"""Narrow regressions for the localhost connection failure, not AI features."""
import logging
import time
import unittest
from unittest.mock import MagicMock, patch

import psycopg
from psycopg_pool import PoolTimeout
import database
import app
from flask import g
from services import auth_service
from services.database_diagnostics import DiagnosticConnection, SafePoolLogFilter, exception_details


class LoginDiagnosisTests(unittest.TestCase):
    def tearDown(self):
        database.close_database_pools()

    def test_failed_login_connect_time_is_recorded_without_checking_password(self):
        def unavailable():
            time.sleep(0.01)
            raise PoolTimeout('private connection info')
        with app.app.test_request_context('/api/auth/login'):
            with patch.object(auth_service, 'get_connection', side_effect=unavailable), patch.object(auth_service, 'check_password_hash') as check:
                with self.assertRaises(PoolTimeout):
                    auth_service.login({'email':'test@example.invalid', 'password':'synthetic'})
                self.assertGreaterEqual(g.login_timings['connect'], 8)
                self.assertEqual(g.login_timings['user_query'], 0)
                check.assert_not_called()

    def test_original_connect_exception_is_logged_without_connection_contents(self):
        private = 'postgresql://private-user:private-password@private-host/private-db'
        with patch.object(psycopg.Connection, 'connect', side_effect=psycopg.errors.ConnectionTimeout(private)):
            with self.assertLogs('reqquality.database', level='ERROR') as captured:
                with self.assertRaises(psycopg.errors.ConnectionTimeout):
                    DiagnosticConnection.connect(private)
        output = '\n'.join(captured.output)
        self.assertIn('ConnectionTimeout', output)
        self.assertIn('driver_connect', output)
        self.assertNotIn(private, output)
        self.assertNotIn('private-password', output)

    def test_pool_default_error_logging_cannot_interpolate_credentials(self):
        record = logging.LogRecord('psycopg.pool', logging.WARNING, '', 1,
                                   'error connecting in %r: %s',
                                   ('pool', psycopg.OperationalError('postgres://user:secret@host/db')), None)
        self.assertTrue(SafePoolLogFilter().filter(record))
        self.assertIn('OperationalError', record.getMessage())
        self.assertNotIn('secret', record.getMessage())
        self.assertNotIn('postgres://', record.getMessage())

    def test_network_auth_schema_and_capacity_failures_are_distinguished(self):
        cases = [(psycopg.errors.ConnectionTimeout('secret'), 'connection_timeout'),
                 (psycopg.errors.InvalidPassword('secret'), 'authentication_rejected'),
                 (psycopg.errors.UndefinedTable('secret'), 'missing_table_or_column'),
                 (psycopg.errors.TooManyConnections('secret'), 'server_connection_limit'),
                 (psycopg.errors.QueryCanceled('secret'), 'query_cancelled_or_timed_out'),
                 (psycopg.OperationalError('secret access permissions 10013'), 'network_access_denied')]
        for error, category in cases:
            details = exception_details(error)
            self.assertEqual(details['category'], category)
            self.assertNotIn('secret', str(details))

    def test_pool_is_lazy_and_does_not_have_five_minute_reconnect_chain(self):
        with patch.object(database, 'ConnectionPool', return_value=MagicMock(closed=False)) as factory:
            database._get_postgres_pool('postgres://test-only')
        options = factory.call_args.kwargs
        self.assertEqual(options['min_size'], 0)
        self.assertEqual(options['reconnect_timeout'], 0)
        self.assertEqual(options['kwargs']['connect_timeout'], 3)
        self.assertEqual(options['timeout'], 10)

    def test_real_pool_failure_chain_stops_and_checkout_has_deadline(self):
        # Real psycopg_pool scheduling, no network or database changes. Its zero
        # reconnect budget allows an immediate final retry, then stops entirely.
        class UnavailableConnection(psycopg.Connection):
            calls = 0

            @classmethod
            def connect(cls, *_args, **_kwargs):
                cls.calls += 1
                raise psycopg.OperationalError('private connection info')

        with patch.object(database, 'DiagnosticConnection', UnavailableConnection), patch.dict('os.environ', DB_POOL_TIMEOUT='0.05'):
            started = time.perf_counter()
            with self.assertLogs(level='WARNING') as captured:
                with self.assertRaises(PoolTimeout):
                    database.connect_database('postgres://test-only', 'must-not-be-created.db')
                elapsed = time.perf_counter()-started
                calls = UnavailableConnection.calls
                time.sleep(0.1)
            self.assertLess(elapsed, 1)
            self.assertGreaterEqual(calls, 1)
            self.assertLessEqual(calls, 2)
            self.assertEqual(UnavailableConnection.calls, calls)
            self.assertNotIn('private connection info', str(captured.output))

    def test_repeated_failed_checkouts_do_not_permanently_fill_waiter_queue(self):
        class UnavailableConnection(psycopg.Connection):
            @classmethod
            def connect(cls, *_args, **_kwargs):
                raise psycopg.OperationalError('private connection info')

        with patch.object(database, 'DiagnosticConnection', UnavailableConnection), patch.dict('os.environ', DB_POOL_TIMEOUT='0.02'), self.assertLogs(level='WARNING'):
            for _ in range(22):
                with self.assertRaises(PoolTimeout):
                    database.connect_database('postgresql://queue-test-only', 'must-not-be-created.db')
                self.assertEqual(database._POSTGRES_POOLS, {})


if __name__ == '__main__':
    unittest.main()
