"""
PostgreSQL Connection Management for Structured Data Integration

Provides safe, connection-pooled database access with proper error handling
and connection lifecycle management.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

logger = logging.getLogger(__name__)

POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")

class StructuredDataConnection:
    """
    Manages PostgreSQL connections with connection pooling and proper error handling.
    
    Provides a safe interface for database operations with automatic connection
    management and retry logic.
    """
    
    def __init__(self,
                 host: Optional[str] = None,
                 database: Optional[str] = None,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 port: Optional[int] = None,
                 min_connections: int = 1,
                 max_connections: int = 10):
        
        self.host = host or POSTGRES_HOST
        self.database = database or POSTGRES_DATABASE
        self.user = user or POSTGRES_USER
        self.password = password or POSTGRES_PASSWORD
        self.port = port or POSTGRES_PORT or 5432
        
        self.min_connections = min_connections
        self.max_connections = max_connections
        
        self._pool = None
        self._connection_params = None
        self._is_connected = False
        
        self._build_connection_params()
    
    def _build_connection_params(self):
        """Build the PostgreSQL connection parameters."""
        self._connection_params = {
            'host': self.host,
            'database': self.database,
            'user': self.user,
            'password': self.password,
            'port': self.port
        }
    
    def connect(self) -> bool:
        """
        Establish connection pool to PostgreSQL.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:            
            self._pool = SimpleConnectionPool(
                minconn=self.min_connections,
                maxconn=self.max_connections,
                **self._connection_params,
                cursor_factory=RealDictCursor
            )
            
            # Test the connection
            with self._pool.getconn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version();")
            
            self._is_connected = True
            logger.info("PostgreSQL connection pool established successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            self._is_connected = False
            return False
    
    def disconnect(self):
        """Close the connection pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            self._is_connected = False
            logger.info("PostgreSQL connection pool closed")
    
    @property
    def is_connected(self) -> bool:
        """Check if the connection is active."""
        return self._is_connected and self._pool is not None
    
    @contextmanager
    def get_connection(self):
        """
        Get a database connection from the pool.
        
        Yields:
            psycopg2.connection: Database connection
            
        Raises:
            ConnectionError: If connection pool is not available
        """
        if not self.is_connected:
            raise ConnectionError("Database connection not established. Call connect() first.")
        
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            if conn:
                self._pool.putconn(conn)
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test the database connection and return status information.
        
        Returns:
            Dict containing connection status and database information
        """
        try:
            if not self.is_connected:
                return {
                    "success": False,
                    "error": "Connection not established",
                    "connected": False
                }
            
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Test basic connectivity
                    cursor.execute("SELECT version();")
                    version = cursor.fetchone()
                    
                    # Get database information
                    cursor.execute("""
                        SELECT 
                            current_database() as database_name,
                            current_user as current_user,
                            inet_server_addr() as server_address,
                            inet_server_port() as server_port
                    """)
                    db_info = cursor.fetchone()
                    
                    # Get table count
                    cursor.execute("""
                        SELECT COUNT(*) as table_count 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                    """)
                    table_count = cursor.fetchone()
                    
                    return {
                        "success": True,
                        "connected": True,
                        "version": version['version'],
                        "database_name": db_info['database_name'],
                        "current_user": db_info['current_user'],
                        "server_address": db_info['server_address'],
                        "server_port": db_info['server_port'],
                        "table_count": table_count['table_count']
                    }
                    
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "connected": False
            }
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute a query and return results as a list of dictionaries.
        
        Args:
            query: SQL query to execute
            params: Query parameters (optional)
            
        Returns:
            List of dictionaries representing query results
            
        Raises:
            ConnectionError: If connection is not available
            Exception: If query execution fails
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                if cursor.description:  # SELECT query
                    return [dict(row) for row in cursor.fetchall()]
                else:  # INSERT, UPDATE, DELETE query
                    conn.commit()
                    return [{"affected_rows": cursor.rowcount}]
    
    def execute_query_single(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """
        Execute a query and return a single result.
        
        Args:
            query: SQL query to execute
            params: Query parameters (optional)
            
        Returns:
            Single dictionary result or None if no results
            
        Raises:
            ConnectionError: If connection is not available
            Exception: If query execution fails
        """
        results = self.execute_query(query, params)
        return results[0] if results else None
    
    def __enter__(self):
        """Context manager entry."""
        if not self.is_connected:
            self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect() 

if __name__ == "__main__":
    connection = StructuredDataConnection()
    connection.connect()
    print(connection.test_connection())
