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

    def test_pool_shutdown_closes_cached_pools(self):
        pool = MagicMock(closed=False)
        with patch.object(database, 'ConnectionPool', return_value=pool):
            database._get_postgres_pool('postgresql://test-only')
            database.close_database_pools()
        pool.close.assert_called_once()
        self.assertEqual(database._POSTGRES_POOLS, {})


if __name__ == '__main__':
    unittest.main()
