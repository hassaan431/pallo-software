import os
import unittest
from unittest.mock import MagicMock, patch
import psycopg2
from psycopg2.extras import RealDictCursor

import database


class TestPostgresConnectionPool(unittest.TestCase):
    def setUp(self):
        # Reset pool state before each test
        database.close_pool()

    def tearDown(self):
        database.close_pool()

    def test_normalize_database_url(self):
        self.assertEqual(database.normalize_database_url(""), "")
        self.assertEqual(database.normalize_database_url(None), "")
        self.assertEqual(
            database.normalize_database_url("postgres://user:pass@host:5432/db"),
            "postgresql://user:pass@host:5432/db",
        )
        self.assertEqual(
            database.normalize_database_url("postgresql://user:pass@host:5432/db?sslmode=require "),
            "postgresql://user:pass@host:5432/db?sslmode=require",
        )

    def test_is_postgres_configured(self):
        with patch.dict(os.environ, {"DATABASE_URL": ""}, clear=True):
            self.assertFalse(database.is_postgres_configured())
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/testdb"}):
            self.assertTrue(database.is_postgres_configured())

    def test_sqlite_fallback_when_database_url_not_set(self):
        with patch.dict(os.environ, {"DATABASE_URL": ""}, clear=True):
            conn = database.get_connection()
            try:
                # Should be sqlite3 connection
                cur = conn.cursor()
                cur.execute("SELECT 1 AS num")
                row = cur.fetchone()
                self.assertEqual(row["num"], 1)
            finally:
                conn.close()

    def test_pooled_connection_wrapper_cursor_factory(self):
        mock_raw_conn = MagicMock()
        mock_pool = MagicMock()
        mock_raw_conn.closed = 0
        mock_raw_conn.status = psycopg2.extensions.STATUS_READY

        wrapper = database.PooledConnectionWrapper(mock_raw_conn, mock_pool)
        wrapper.cursor()
        mock_raw_conn.cursor.assert_called_once_with(cursor_factory=RealDictCursor)

    def test_pooled_connection_wrapper_close_returns_to_pool(self):
        mock_raw_conn = MagicMock()
        mock_pool = MagicMock()
        mock_raw_conn.closed = 0
        mock_raw_conn.status = psycopg2.extensions.STATUS_READY

        wrapper = database.PooledConnectionWrapper(mock_raw_conn, mock_pool)
        wrapper.close()

        # Should NOT call raw_conn.close()
        mock_raw_conn.close.assert_not_called()
        # Should call pool.putconn()
        mock_pool.putconn.assert_called_once_with(mock_raw_conn)

        # Idempotent close check
        wrapper.close()
        self.assertEqual(mock_pool.putconn.call_count, 1)

    def test_pooled_connection_wrapper_rollback_on_dirty_transaction(self):
        mock_raw_conn = MagicMock()
        mock_pool = MagicMock()
        mock_raw_conn.closed = 0
        # Transaction in progress (STATUS_IN_TRANSACTION)
        mock_raw_conn.status = psycopg2.extensions.STATUS_IN_TRANSACTION

        wrapper = database.PooledConnectionWrapper(mock_raw_conn, mock_pool)
        wrapper.close()

        # Should rollback dirty transaction before returning to pool
        mock_raw_conn.rollback.assert_called_once()
        mock_pool.putconn.assert_called_once_with(mock_raw_conn)

    def test_get_db_connection_context_manager(self):
        mock_raw_conn = MagicMock()
        mock_pool = MagicMock()
        mock_raw_conn.closed = 0
        mock_raw_conn.status = psycopg2.extensions.STATUS_READY

        with patch.object(database, "is_postgres_configured", return_value=True), \
             patch.object(database, "get_pool", return_value=mock_pool):
            mock_pool.getconn.return_value = mock_raw_conn

            with database.get_db_connection() as conn:
                self.assertIsInstance(conn, database.PooledConnectionWrapper)

            mock_pool.putconn.assert_called_once_with(mock_raw_conn)

    def test_get_db_cursor_context_manager(self):
        mock_raw_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool = MagicMock()
        mock_raw_conn.closed = 0
        mock_raw_conn.status = psycopg2.extensions.STATUS_READY
        mock_raw_conn.cursor.return_value = mock_cursor

        with patch.object(database, "is_postgres_configured", return_value=True), \
             patch.object(database, "get_pool", return_value=mock_pool):
            mock_pool.getconn.return_value = mock_raw_conn

            with database.get_db_cursor(commit=True) as cur:
                cur.execute("SELECT 1")

            mock_cursor.execute.assert_called_once_with("SELECT 1")
            mock_cursor.close.assert_called_once()
            mock_raw_conn.commit.assert_called_once()
            mock_pool.putconn.assert_called_once_with(mock_raw_conn)


if __name__ == "__main__":
    unittest.main()
