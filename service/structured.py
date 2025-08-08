"""
Hybrid Search Service

Combines structured data search (PostgreSQL) with unstructured data search (Neo4j GraphRAG)
to provide comprehensive search capabilities across both data types.
"""

import logging
from typing import List, Dict, Any

from .connection import StructuredDataConnection
from .schema import DatabaseSchema
from utils.functions import format_result

logger = logging.getLogger(__name__)

class StructuredService:
    """
    Service that combines structured and unstructured search capabilities.
    
    Provides:
    - Intelligent query routing to appropriate search types
    - Result combination and ranking
    - Unified response formatting
    """
    
    def __init__(self, structured_connection: StructuredDataConnection = None):
        """
        Initialize the hybrid search service.
        
        Args:
            structured_connection: Optional pre-configured structured data connection
        """
        self.structured_connection = structured_connection
        self.structured_search_engine = None
        self.memory = []
        
        # Initialize structured search components if connection is available
        if self.structured_connection:
            self.initialize_structured_search()
        
        logger.info("StructuredSearchService initialized")
    
    def initialize_structured_search(self):
        """Initialize structured search components."""
        try:
            # Discover database schema
            self.schema = DatabaseSchema(self.structured_connection)
            # Optionally, discover schema metadata if needed
            # metadata = self.schema.discover_schema()  # Not implemented, so skip
            # Initialize search engine
            self.structured_search_engine = self.structured_connection
            return True
        except Exception as e:
            logger.error(f"Failed to initialize structured search: {e}")
            self.structured_search_engine = None
            return False
        
    def set_structured_connection(self, connection: StructuredDataConnection):
        """Set the structured data connection and initialize components."""
        self.structured_connection = connection
        self.initialize_structured_search()

    def list_tables(self) -> List[str]:
        """List all tables in the database."""
        return self.schema.list_tables()
    
    def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """Get the columns for a given table."""
        return self.schema.get_table_columns(table_name)
    
    def get_sample_rows(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample rows from a table."""
        return self.schema.get_sample_rows(table_name, limit)
    
    def custom_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a custom query on the database."""
        return self.schema.custom_query(query)