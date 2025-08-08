from dataclasses import dataclass
from typing import List
from pydantic import BaseModel

@dataclass
class Document:
    """Represents a document in the knowledge graph"""
    id: str
    title: str
    content: str
    file_path: str


@dataclass
class Chunk:
    """Represents a text chunk extracted from documents"""
    id: str
    text: str
    n_tokens: int
    document_ids: List[str]


@dataclass
class Entity:
    """Represents an entity extracted from text"""
    id: str
    human_readable_id: int
    title: str
    type: str
    description: str
    text_unit_ids: List[str]
    frequency: int = 0
    degree: int = 0
    x: float = 0.0
    y: float = 0.0


@dataclass
class Relationship:
    """Represents a relationship between entities"""
    id: str
    human_readable_id: int
    source: str
    target: str
    description: str
    weight: float
    text_unit_ids: List[str]
    combined_degree: int = 0


@dataclass
class Community:
    """Represents a community of related entities"""
    id: str
    level: int
    title: str
    text_unit_ids: List[str]
    relationship_ids: List[str] 

class HybridSearchRequest(BaseModel):
    query: str
    search_type: str
    response_type: str
    user_email: str
    document_titles: list[str] = None