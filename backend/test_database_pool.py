"""Pooled adapter resource and transaction regression tests."""
import unittest
from unittest.mock import MagicMock, patch
import database


class DatabasePoolTests(unittest.TestCase):
    def tearDown(self):
        database.close_database_pools()

    def test_pool_is_reused_and_connections_are_returned_once(self):
        pool = MagicMock(closed=False)
        with patch.object(database, 'ConnectionPool', return_value=pool) as factory:
            first = database.connect_database('postgres://test-only', 'unused')
            second = database.connect_database('postgresql://test-only', 'unused')
            factory.assert_called_once()
            self.assertEqual(factory.call_args.kwargs['conninfo'], 'postgresql://test-only')
            self.assertEqual(pool.getconn.call_count, 2)
            first.close()
            first.close()
            second.close()
            self.assertEqual(pool.putconn.call_count, 2)
            pool.getconn.return_value.close.assert_not_called()

    def test_released_adapter_cannot_access_a_connection_borrowed_by_another_request(self):
        raw = MagicMock()
        adapter = database.DatabaseConnection(raw, 'postgres', pool=MagicMock())
        adapter.close()
        for operation in [lambda: adapter.execute('SELECT 1'), adapter.commit, adapter.__enter__]:
            with self.assertRaises(database.psycopg.InterfaceError):
                operation()
        raw.execute.assert_not_called()
        raw.commit.assert_not_called()

    def test_database_urls_have_separate_pools(self):
        with patch.object(database, 'ConnectionPool', side_effect=lambda **kw: MagicMock(closed=False)) as factory:
            a = database.connect_database('postgresql://a-test-only', 'unused')
            b = database.connect_database('postgresql://b-test-only', 'unused')
            self.assertEqual(factory.call_count, 2)
            a.close(); b.close()

    def test_read_mode_restores_autocommit_after_success_and_exception(self):
        raw = MagicMock(autocommit=False)
        adapter = database.DatabaseConnection(raw, 'postgres', pool=MagicMock())
        with adapter.autocommit_reads():
            self.assertTrue(raw.autocommit)
        self.assertFalse(raw.autocommit)
        with self.assertRaises(ValueError):
            with adapter.autocommit_reads():
                self.assertTrue(raw.autocommit)
                raise ValueError('failed read')
        self.assertFalse(raw.autocommit)

    def test_sqlite_read_mode_does_not_change_driver_state(self):
        raw = MagicMock(spec=['execute', 'close'])
        adapter = database.DatabaseConnection(raw, 'sqlite')
        with adapter.autocommit_reads() as connection:
            self.assertIs(connection, adapter)
        self.assertFalse(hasattr(raw, 'autocommit'))

    def test_existing_transaction_context_reaches_psycopg(self):
        raw = MagicMock()
        adapter = database.DatabaseConnection(raw, 'postgres', pool=MagicMock())
        with adapter:
            adapter.execute('INSERT INTO example VALUES (?)', (1,))
        raw.__enter__.assert_called_once()
        raw.__exit__.assert_called_once_with(None, None, None)
        raw.execute.assert_called_once_with('INSERT INTO example VALUES (%s)', (1,))

    def test_exception_reaches_driver_rollback_context(self):
        raw = MagicMock()
        raw.__exit__.return_value = False
        adapter = database.DatabaseConnection(raw, 'postgres', pool=MagicMock())
        with self.assertRaises(ValueError):
            with adapter:
                raise ValueError('rollback')
        self.assertIs(raw.__exit__.call_args.args[0], ValueError)

    def test_installed_psycopg_context_preserves_pool_socket_between_login_transactions(self):
        # Real installed driver context behavior, with mocked network/connection.
        raw = MagicMock(closed=False, _pool=MagicMock())
        raw.__exit__.side_effect = lambda *args: database.psycopg.Connection.__exit__(raw, *args)
        pool = MagicMock()
        adapter = database.DatabaseConnection(raw, 'postgres', pool=pool)
        with adapter:
            adapter.execute('SELECT 1')
        with adapter.autocommit_reads():
            adapter.execute('SELECT 1')
        with adapter:
            adapter.execute('SELECT 1')
        self.assertEqual(raw.commit.call_count, 2)
        raw.close.assert_not_called()
        adapter.close()
        pool.putconn.assert_called_once_with(raw)

    def test_pool_shutdown_closes_cached_pools(self):
        pool = MagicMock(closed=False)
        with patch.object(database, 'ConnectionPool', return_value=pool):
            database._get_postgres_pool('postgresql://test-only')
            database.close_database_pools()
        pool.close.assert_called_once()
        self.assertEqual(database._POSTGRES_POOLS, {})

    def test_pool_bounds_waiters_without_injecting_unsupported_startup_options(self):
        with patch.object(database, 'ConnectionPool', return_value=MagicMock(closed=False)) as factory:
            database._get_postgres_pool('postgresql://test-only/db?options=-c%20application_name%3Dreqquality')
        options = factory.call_args.kwargs
        self.assertEqual(options['max_waiting'], 20)
        self.assertIs(options['check'], database._check_idle_connection)
        self.assertNotIn('options', options['kwargs'])
        self.assertIn('application_name', options['conninfo'])

    def test_idle_socket_is_checked_but_warm_checkout_has_no_extra_query(self):
        raw = MagicMock(closed=False)
        raw._reqquality_returned_at = 100
        with patch.object(database, 'monotonic', return_value=129), patch.object(database.ConnectionPool, 'check_connection') as check:
            database._check_idle_connection(raw)
            check.assert_not_called()
        with patch.object(database, 'monotonic', return_value=130), patch.object(database.ConnectionPool, 'check_connection') as check:
            database._check_idle_connection(raw)
            check.assert_called_once_with(raw)

    def test_return_records_idle_time_and_failed_check_reaches_pool_recovery(self):
        raw = MagicMock(closed=False)
        pool = MagicMock()
        adapter = database.DatabaseConnection(raw, 'postgres', pool=pool)
        with patch.object(database, 'monotonic', return_value=100):
            adapter.close()
        self.assertEqual(raw._reqquality_returned_at, 100)
        pool.putconn.assert_called_once_with(raw)
        with patch.object(database, 'monotonic', return_value=140), patch.object(database.ConnectionPool, 'check_connection', side_effect=database.psycopg.OperationalError('test disconnect')):
            with self.assertRaises(database.psycopg.OperationalError):
                database._check_idle_connection(raw)

    def test_checkout_timeout_never_retires_pool_with_live_or_connecting_sockets(self):
        pool = MagicMock(closed=False)
        pool.getconn.side_effect = database.PoolTimeout('test saturation')
        pool.get_stats.return_value = {'pool_size': 1}
        with patch.object(database, 'ConnectionPool', return_value=pool), self.assertLogs('reqquality.database', level='ERROR'):
            with self.assertRaises(database.PoolTimeout):
                database.connect_database('postgresql://live-test-only', 'unused.db')
        pool.close.assert_not_called()
        self.assertIn(pool, database._POSTGRES_POOLS.values())


if __name__ == '__main__':
    unittest.main()
