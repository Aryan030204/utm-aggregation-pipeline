import hashlib

import mysql.connector
from mysql.connector import Error
from app.utils.logger import get_logger

logger = get_logger(__name__)

class DBManager:
    def __init__(self, brand_name: str, host: str, user: str, password: str, database: str, port: int = 3306):
        self.brand = brand_name
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.connection = None

    def connect(self):
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                connection_timeout=10
            )
            if self.connection.is_connected():
                logger.debug(f"Connected to database '{self.database}' for brand '{self.brand}'")
            return self.connection
        except Error as e:
            logger.error(f"Error while connecting to MySQL database '{self.database}' ({self.host}): {e}")
            raise e

    def close(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()

    def _ensure_connected(self):
        if not self.connection or not self.connection.is_connected():
            self.connect()

    def execute_query(self, query: str, params: tuple = None, commit=False):
        self._ensure_connected()

        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            if commit:
                self.connection.commit()
                return cursor.rowcount
            else:
                return cursor.fetchall()
        except Error as e:
            logger.error(f"Error executing query: {e}")
            if commit:
                self.connection.rollback()
            raise e
        finally:
            cursor.close()

    def fetch_all(self, query: str, params: tuple = None):
        """Runs a read query and immediately ends its implicit transaction, so no
        consistent-read snapshot is held while the caller does slow work (e.g. Shopify
        fetches) before its next statement."""
        self._ensure_connected()
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        except Error as e:
            logger.error(f"Error executing query: {e}")
            raise e
        finally:
            cursor.close()
        self.connection.commit()
        return rows

    def begin(self):
        self._ensure_connected()
        if self.connection.in_transaction:
            self.connection.rollback()
        self.connection.start_transaction()

    def execute_write(self, query: str, params: tuple = None) -> int:
        """Runs a write statement inside the caller's open transaction (no commit)."""
        self._ensure_connected()
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params)
            return cursor.rowcount
        finally:
            cursor.close()

    def commit(self):
        self.connection.commit()

    def rollback(self):
        if self.connection and self.connection.is_connected():
            self.connection.rollback()

    @staticmethod
    def lock_name(database: str) -> str:
        """Advisory lock name for a brand database (MySQL caps lock names at 64 chars)."""
        return "utm_agg:" + hashlib.md5(database.encode("utf-8")).hexdigest()

    def try_lock(self, name: str, timeout_seconds: int = 0) -> bool:
        """GET_LOCK is held by this connection's session until released or closed."""
        rows = self.fetch_all("SELECT GET_LOCK(%s, %s) AS acquired", (name, timeout_seconds))
        return bool(rows) and rows[0]["acquired"] == 1

    def release_lock(self, name: str) -> None:
        if not self.connection or not self.connection.is_connected():
            return
        try:
            self.fetch_all("SELECT RELEASE_LOCK(%s) AS released", (name,))
        except Error as e:
            logger.warning(f"Could not release lock '{name}' (it is freed when the connection closes): {e}")
