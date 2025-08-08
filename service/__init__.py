"""
Structured Data Integration for GraphRAG

This module provides integration with structured data sources (PostgreSQL)
to enhance the GraphRAG query capabilities with database-driven insights.
"""

from .connection import StructuredDataConnection
from .structured import StructuredService
from .unstructured import UnstructuredService
__version__ = "1.0.0"
__all__ = [
    "StructuredDataConnection",
    "StructuredService",
    "UnstructuredService"
] 