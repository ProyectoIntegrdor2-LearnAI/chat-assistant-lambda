import os
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor


class PostgresClient:
    def __init__(self) -> None:
        host = os.getenv("POSTGRES_HOST")
        password = os.getenv("POSTGRES_PASSWORD")
        if not host or not password:
            raise ValueError("POSTGRES_HOST and POSTGRES_PASSWORD env vars are required")

        self._db = os.getenv("POSTGRES_DB", "postgres")
        self._user = os.getenv("POSTGRES_USER", "postgres")
        self._port = int(os.getenv("POSTGRES_PORT", "5432"))
        self._min_conn = int(os.getenv("POSTGRES_POOL_MIN", "1"))
        self._max_conn = int(os.getenv("POSTGRES_POOL_MAX", "5"))
        self._ssl_enabled = os.getenv("DB_SSL", "true").lower() == "true"
        self._pool: Optional[pool.SimpleConnectionPool] = None

    def _create_pool(self) -> pool.SimpleConnectionPool:
        kwargs = {
            "host": os.getenv("POSTGRES_HOST"),
            "port": self._port,
            "dbname": self._db,
            "user": self._user,
            "password": os.getenv("POSTGRES_PASSWORD"),
            "connect_timeout": 5,
        }
        if self._ssl_enabled:
            kwargs["sslmode"] = "require"
            ca_path = os.getenv("DB_CA_PATH")
            if ca_path:
                kwargs["sslrootcert"] = ca_path

        return pool.SimpleConnectionPool(self._min_conn, self._max_conn, **kwargs)

    def _get_pool(self) -> pool.SimpleConnectionPool:
        if self._pool is None:
            self._pool = self._create_pool()
        return self._pool

    @contextmanager
    def connection(self):
        conn = self._get_pool().getconn()
        try:
            yield conn
        finally:
            self._get_pool().putconn(conn)

    def fetch_learning_path(
        self, user_id: str, learning_path_id: str
    ) -> Optional[Dict[str, Any]]:
        query = """
            SELECT
                path_id,
                name,
                description,
                status,
                progress_percentage,
                target_hours_per_week,
                target_completion_date,
                priority,
                is_public,
                created_at,
                updated_at,
                completed_at
            FROM user_learning_paths
            WHERE user_id = %s AND path_id = %s
            LIMIT 1
        """
        with self.connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (user_id, learning_path_id))
            row = cur.fetchone()
        if not row:
            return None
        return dict(row)

    def fetch_courses(
        self, user_id: str, learning_path_id: str
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT
                mongodb_course_id,
                status,
                progress_percentage,
                sequence_order,
                time_invested_minutes,
                started_at,
                completed_at,
                updated_at
            FROM course_progress
            WHERE user_id = %s AND path_id = %s
            ORDER BY sequence_order
        """
        with self.connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (user_id, learning_path_id))
            rows = cur.fetchall()
        return [dict(row) for row in rows]


_client: Optional[PostgresClient] = None


def get_postgres_client() -> PostgresClient:
    global _client
    if _client is None:
        _client = PostgresClient()
    return _client
