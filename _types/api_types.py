from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class BaseResponse(BaseModel):
    """Base response model for all API endpoints"""
    success: bool = Field(..., description="Whether the operation was successful")
    message: Optional[str] = Field(None, description="Response message")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class HealthResponse(BaseResponse):
    """Response model for health check endpoint"""
    timestamp: str = Field(..., description="Current timestamp")
    neo4j_uri: Optional[str] = Field(None, description="Neo4j connection URI")
    neo4j_database: Optional[str] = Field(None, description="Neo4j database name")
    service_initialized: bool = Field(..., description="Whether the service is initialized")
    database_connected: Optional[bool] = Field(None, description="Database connection status")
    database_error: Optional[str] = Field(None, description="Database error if any")


class IngestResponse(BaseResponse):
    """Response model for document ingestion endpoint"""
    files_processed: int = Field(..., description="Number of files processed")
    file_names: List[str] = Field(..., description="Names of processed files")
    documents_processed: Optional[int] = Field(None, description="Number of documents processed")
    chunks_created: Optional[int] = Field(None, description="Number of chunks created")
    entities_extracted: Optional[int] = Field(None, description="Number of entities extracted")
    relationships_detected: Optional[int] = Field(None, description="Number of relationships detected")
    communities_detected: Optional[int] = Field(None, description="Number of communities detected")


class QueryResponse(BaseResponse):
    """Response model for query endpoint"""
    query: str = Field(..., description="The original query")
    search_type: str = Field(..., description="Type of search performed")
    response_type: str = Field(..., description="Type of response format")
    response: Optional[str] = Field(None, description="Generated response")
    context_data: Optional[Dict[str, Any]] = Field(None, description="Context data used for response")


class ClearResponse(BaseResponse):
    """Response model for database clear endpoint"""
    nodes_cleared: int = Field(..., description="Number of nodes cleared")
    relationships_cleared: int = Field(..., description="Number of relationships cleared")


class UpdateResponse(BaseResponse):
    """Response model for knowledge graph update endpoint"""
    new_documents_added: Optional[int] = Field(None, description="Number of new documents added")
    new_chunks_created: Optional[int] = Field(None, description="Number of new chunks created")
    total_entities: Optional[int] = Field(None, description="Total number of entities")
    total_relationships: Optional[int] = Field(None, description="Total number of relationships")
    communities_updated: Optional[int] = Field(None, description="Number of communities updated") 