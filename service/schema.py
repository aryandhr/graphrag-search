import logging
from typing import List, Dict, Any
from .connection import StructuredDataConnection

logger = logging.getLogger(__name__)

class DatabaseSchema:
    def __init__(self, connection: StructuredDataConnection):
        self.connection = connection

    def list_tables(self) -> List[str]:
        """Return a list of table names in the public schema."""
        query = """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
        """
        try:
            results = self.connection.execute_query(query)
            return [row['table_name'] for row in results]
        except Exception as e:
            logger.error(f"Error listing tables: {e}")
            return []

    def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """Return columns and types for a given table."""
        query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s;
        """
        try:
            results = self.connection.execute_query(query, (table_name,))
            return results
        except Exception as e:
            logger.error(f"Error getting columns for {table_name}: {e}")
            return []

    def get_sample_rows(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Return sample rows from a table."""
        query = f"SELECT * FROM \"{table_name}\" LIMIT %s;"
        try:
            results = self.connection.execute_query(query, (limit,))
            return results
        except Exception as e:
            logger.error(f"Error getting sample rows for {table_name}: {e}")
            return []
        
    def custom_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a custom query on the database."""
        try:
            results = self.connection.execute_query(query)
            return results
        except Exception as e:
            logger.error(f"Error executing custom query: {e}")
            return {"error": str(e)}