from pydantic import BaseModel, Field
from typing import Optional


class QueryRequest(BaseModel):
    """
    Request model for querying the knowledge graph
    
    Attributes:
        query (str): The search query string
    """
    query: str = Field(..., description="The search query string", min_length=1)
    email: str = Field(..., description="The email of the user")

    