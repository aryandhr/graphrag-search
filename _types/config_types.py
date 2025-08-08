from pydantic import BaseModel, Field
from typing import Optional


class Neo4jConfig(BaseModel):
    """Neo4j database configuration"""
    uri: str = Field(..., description="Neo4j connection URI")
    username: str = Field(..., description="Neo4j username")
    password: str = Field(..., description="Neo4j password")
    database: str = Field(..., description="Neo4j database name")


class ProcessingConfig(BaseModel):
    """Document processing configuration"""
    chunk_size: int = Field(default=1000, description="Size of text chunks in tokens")
    chunk_overlap: int = Field(default=200, description="Overlap between chunks in tokens")
    entity_types: Optional[list[str]] = Field(default=None, description="Types of entities to extract")


class SearchConfig(BaseModel):
    """Search configuration"""
    community_level: int = Field(default=2, description="Community level for search")
    dynamic_community_selection: bool = Field(default=False, description="Whether to use dynamic community selection")
    response_type: str = Field(default="Multiple Paragraphs", description="Type of response format")


class AppConfig(BaseModel):
    """Main application configuration"""
    neo4j: Neo4jConfig = Field(..., description="Neo4j configuration")
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig, description="Processing configuration")
    search: SearchConfig = Field(default_factory=SearchConfig, description="Search configuration") 