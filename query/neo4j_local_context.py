# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Neo4j-based Local Search Context Builder for GraphRAG."""

import logging
import random
from typing import Any, cast
from graphrag.query.context_builder.builders import ContextBuilderResult
from graphrag.query.context_builder.conversation_history import ConversationHistory
from graphrag.query.structured_search.base import LocalContextBuilder
from graphrag.query.llm.text_utils import num_tokens

import pandas as pd
import tiktoken
from neo4j import GraphDatabase
import numpy as np
import openai
import os
from dotenv import load_dotenv
from utils.functions import embed, cosine_similarity

if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

logger = logging.getLogger(__name__)

NO_CHUNK_RECORDS_WARNING: str = (
    "Warning: No chunk records added when building local context."
)


class Neo4jLocalContext(LocalContextBuilder):
    """Neo4j-based LocalSearch context builder."""

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        token_encoder: tiktoken.Encoding | None = None,
        random_state: int = 86,
        openai_api_key: str = os.getenv("OPENAI_API_KEY"),
        openai_model: str = "text-embedding-3-small",
        user_email: str = None,
    ):
        """Initialize the Neo4j context builder.
        
        Args:
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            token_encoder: Token encoder for counting tokens
            random_state: Random seed for reproducibility
            openai_api_key: OpenAI API key for embeddings
            openai_model: OpenAI embedding model to use
            user_email: User email to filter data by
        """
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.token_encoder = token_encoder
        self.random_state = random_state
        self.openai_client = openai.OpenAI(api_key=openai_api_key) if openai_api_key else None
        self.openai_model = openai_model
        self.user_email = user_email

    def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()

    async def build_context(
        self,
        query: str,
        conversation_history: ConversationHistory | None = None,
        column_delimiter: str = "|",
        shuffle_data: bool = True,
        max_context_tokens: int = 8000,
        context_name: str = "Chunks",
        conversation_history_user_turns_only: bool = True,
        conversation_history_max_turns: int | None = 5,
        **kwargs: Any,
    ) -> ContextBuilderResult:
        """Prepare chunks and entities from Neo4j as context data for local search."""
        
        conversation_history_context = ""
        final_context_data = {}
        llm_calls, prompt_tokens, output_tokens = 0, 0, 0
        
        if conversation_history:
            # build conversation history context
            (
                conversation_history_context,
                conversation_history_context_data,
            ) = conversation_history.build_context(
                include_user_turns_only=conversation_history_user_turns_only,
                max_qa_turns=conversation_history_max_turns,
                column_delimiter=column_delimiter,
                max_context_tokens=max_context_tokens,
                recency_bias=False,
            )
            if conversation_history_context != "":
                final_context_data = conversation_history_context_data

        # Get chunks and entities from Neo4j
        chunks_data = self.get_chunks_from_neo4j(query=query, relevance_score_threshold=0.3)

        # Build context using the chunks data
        chunks_context, chunks_context_data = self._build_chunks_context(
            chunks_data=chunks_data,
            column_delimiter=column_delimiter,
            shuffle_data=shuffle_data,
            max_context_tokens=max_context_tokens,
            context_name=context_name,
        )

        # Prepare context_prefix based on whether conversation_history_context exists
        context_prefix = (
            f"{conversation_history_context}\n\n"
            if conversation_history_context
            else ""
        )

        final_context = (
            [f"{context_prefix}{context}" for context in chunks_context]
            if isinstance(chunks_context, list)
            else f"{context_prefix}{chunks_context}"
        )

        # Update the final context data with the provided chunks_context_data
        final_context_data.update(chunks_context_data)

        return ContextBuilderResult(
            context_chunks=final_context,
            context_records=final_context_data,
            llm_calls=llm_calls,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
        )

    def get_chunks_from_neo4j(self, query: str, relevance_score_threshold: float = 0.3, document_type: str | None = None) -> list[dict]:
        """Retrieve chunks and their associated entities from Neo4j database.
        
        This method queries the Neo4j database to get chunks that are
        relevant to the search query using similarity search.
        """

        if not self.user_email:
            raise ValueError("User email is required")
        if not self.openai_client:
                raise ValueError("OpenAI API key is required")
                
        with self.driver.session() as session:
            # Build the WHERE clause conditionally
            doc_type_filter = "WHERE doc.type = $document_type" if document_type else ""
            
            cypher_query = f"""
                MATCH (chunk:__Chunk__ {{userEmail: $user_email}})
                OPTIONAL MATCH (chunk)-[:HAS_ENTITY]->(entity:__Entity__ {{userEmail: $user_email}})
                OPTIONAL MATCH (chunk)-[:PART_OF]->(doc:__Document__ {{userEmail: $user_email}})
                {doc_type_filter}
                
                WITH chunk, 
                    collect(DISTINCT entity.name) as entity_names,
                    collect(DISTINCT entity.description) as entity_descriptions,
                    collect(DISTINCT entity.type) as entity_types,
                    collect(DISTINCT doc.title) as document_titles
                
                RETURN {{
                    id: chunk.id,
                    text: chunk.text,
                    n_tokens: chunk.n_tokens,
                    entity_names: entity_names,
                    entity_descriptions: entity_descriptions,
                    entity_types: entity_types,
                    document_titles: document_titles,
                    embedding: chunk.embedding,
                    relevance_score: 0
                }} as chunk_data
                ORDER BY chunk.id
            """

            result = session.run(cypher_query, user_email=self.user_email, document_type=document_type)
            
            chunks = [record["chunk_data"] for record in result]

            if chunks:
                logger.info(f"CALCULATING SIMILARITY SCORES USING OPENAI (using precomputed chunk embedding)")
                try:
                    query_embedding = embed(query, self.openai_model)
                    
                    similarities = []
                    for chunk in chunks:
                        chunk_embedding = chunk.get("embedding")
                        similarity = cosine_similarity(query_embedding, chunk_embedding)
                        similarities.append(float(similarity))
                    
                    for chunk, similarity in zip(chunks, similarities):
                        chunk["relevance_score"] = similarity
                    
                    chunks.sort(key=lambda x: x["relevance_score"], reverse=True)
                    chunks = [chunk for chunk in chunks if chunk["relevance_score"] >= relevance_score_threshold]
                
                except Exception as e:
                    logger.warning(f"Failed to calculate embedding using OpenAI: {e}")
                    pass
            return chunks
        
    def get_top_k_documents(self, query: str, k: int = 5, document_type: str | None = None) -> list[str]:
        """Retrieve the top k documents from Neo4j database."""
        top_k_docs = {}
        chunks = self.get_chunks_from_neo4j(query=query, document_type=document_type)
       
        for chunk in chunks:
            doc_title = chunk.get("document_titles")[0]
            chunk_relevance_score = chunk.get("relevance_score")
            if doc_title in top_k_docs:
                top_k_docs[doc_title] += chunk_relevance_score
            else:
                top_k_docs[doc_title] = chunk_relevance_score
        
        sorted_docs = sorted(top_k_docs.items(), key=lambda x: x[1], reverse=True)
        return [doc_title for doc_title, count in sorted_docs[:k]]
    
    def _build_chunks_context(
        self,
        chunks_data: list[dict],
        column_delimiter: str = "|",
        shuffle_data: bool = True,
        max_context_tokens: int = 8000,
        context_name: str = "Chunks",
    ) -> tuple[str | list[str], dict[str, pd.DataFrame]]:
        """Build context from chunks data."""
        
        if not chunks_data:
            logger.warning(NO_CHUNK_RECORDS_WARNING)
            return "", {}

        def _is_included(chunk: dict) -> bool:
            # Include all chunks that have some content
            return bool(chunk.get("text", "").strip())

        def _get_header() -> list[str]:
            return [
                "id",
                "text",
                "entity_names",
                "entity_descriptions", 
                "entity_types",
                "document_titles",
                "relevance_score"
            ]

        def _chunk_context_text(chunk: dict) -> tuple[str, list[str]]:
            # Format chunk data as text
            entity_names_str = ", ".join(chunk.get("entity_names", []))
            entity_descriptions_str = "; ".join(chunk.get("entity_descriptions", []))
            entity_types_str = ", ".join(chunk.get("entity_types", []))
            document_titles_str = ", ".join(chunk.get("document_titles", []))
            
            context_text = f"Chunk ID: {chunk.get('id', '')}\n"
            context_text += f"Text: {chunk.get('text', '')}\n"
            context_text += f"Entities: {entity_names_str}\n"
            context_text += f"Entity Descriptions: {entity_descriptions_str}\n"
            context_text += f"Entity Types: {entity_types_str}\n"
            context_text += f"Documents: {document_titles_str}\n"
            context_text += f"Relevance Score: {chunk.get('relevance_score', 0)}\n"
            
            # Create record for DataFrame
            record = [
                chunk.get("id", ""),
                chunk.get("text", ""),
                entity_names_str,
                entity_descriptions_str,
                entity_types_str,
                document_titles_str,
                chunk.get("relevance_score", 0)
            ]
            return context_text, record

        # Initialize variables
        current_context = []
        current_records = []
        current_tokens = 0
        context_data = {}

        # Filter and process chunks
        included_chunks = [chunk for chunk in chunks_data if _is_included(chunk)]
        logger.info(f"INCLUDED CHUNKS!!!!!!!!!!!!: {included_chunks[0].get('id')}")
        for chunk in included_chunks:
            context_text, record = _chunk_context_text(chunk)
            
            # Count tokens in this chunk
            chunk_tokens = num_tokens(context_text, self.token_encoder) if self.token_encoder else len(context_text.split())
            
            # Check if adding this chunk would exceed the token limit
            if current_tokens + chunk_tokens > max_context_tokens and current_context:
                break
            
            current_context.append(context_text)
            current_records.append(record)
            current_tokens += chunk_tokens

        # Combine all context chunks
        final_context = "\n\n---\n\n".join(current_context) if current_context else ""
        return final_context, context_data 