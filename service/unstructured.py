from pathlib import Path
from graphrag.config.load_config import load_config
from query.neo4j_global_search_api import neo4j_global_search
from query.neo4j_local_search_api import neo4j_local_search
from query.neo4j_local_context import Neo4jLocalContext
from typing import Dict, Any
from dotenv import load_dotenv
import os
import logging
from neo4j import GraphDatabase

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UnstructuredService:    
    def __init__(self):
        self.config = None
        self._load_config()
    
    def _load_config(self):
        """Load GraphRAG configuration"""
        try:
            root_dir = Path("./query/ragtest")
            config_filepath = Path("query/ragtest/settings.yaml")
            self.config = load_config(root_dir, config_filepath, {})
            logger.info("Successfully loaded GraphRAG configuration")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def initialize_neo4j_local_context(self, user_email: str):
        try:
            self.neo4j_local_context = Neo4jLocalContext(
                neo4j_uri=os.getenv("NEO4J_URI"),
                neo4j_user=os.getenv("NEO4J_USERNAME"),
                neo4j_password=os.getenv("NEO4J_PASSWORD"),
                user_email=user_email
            )
            logger.info("Successfully initialized Neo4j local context")
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j local context: {e}")
            raise

    def initialize_schema(self) -> Dict[str, Any]:
        """Initialize database schema with required constraints and indexes"""
        try:
            driver = GraphDatabase.driver(
                os.getenv("NEO4J_URI"), 
                auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
            )
            
            # Create constraints and indexes for better performance
            schema_queries = [
                # Create unique constraints
                "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:__Document__) REQUIRE d.id IS UNIQUE",
                "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:__Chunk__) REQUIRE c.id IS UNIQUE",
                "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:__Entity__) REQUIRE e.id IS UNIQUE",
                "CREATE CONSTRAINT community_id_unique IF NOT EXISTS FOR (c:__Community__) REQUIRE c.community IS UNIQUE",
                
                # Create indexes for better query performance
                "CREATE INDEX document_title_index IF NOT EXISTS FOR (d:__Document__) ON (d.title)",
                "CREATE INDEX entity_name_index IF NOT EXISTS FOR (e:__Entity__) ON (e.name)",
                "CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:__Entity__) ON (e.type)",
                "CREATE INDEX relationship_id_index IF NOT EXISTS FOR ()-[r:RELATED]-() ON (r.id)",
                
                # Create indexes for user email filtering
                "CREATE INDEX document_user_email_index IF NOT EXISTS FOR (d:__Document__) ON (d.userEmail)",
                "CREATE INDEX chunk_user_email_index IF NOT EXISTS FOR (c:__Chunk__) ON (c.userEmail)",
                "CREATE INDEX entity_user_email_index IF NOT EXISTS FOR (e:__Entity__) ON (e.userEmail)",
                "CREATE INDEX community_user_email_index IF NOT EXISTS FOR (c:__Community__) ON (c.userEmail)",
                "CREATE INDEX relationship_user_email_index IF NOT EXISTS FOR ()-[r:RELATED]-() ON (r.userEmail)"
            ]
            
            for query in schema_queries:
                try:
                    driver.execute_query(query, database_=os.getenv("NEO4J_DATABASE"))
                except Exception as e:
                    # Some constraints might already exist, which is fine
                    logger.debug(f"Schema query warning (may already exist): {e}")
            
            driver.close()
            
            return {
                "success": True,
                "message": "Unstructured search schema initialized"
            }
            
        except Exception as e:
            logger.error(f"Error initializing unstructured search schema: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def global_search(self, query: str, response_type: str = "Multiple Paragraphs", user_email: str = None) -> Dict[str, Any]:
        """Perform global search using the actual GraphRAG implementation"""
        try:
            response, context_data = await neo4j_global_search(
                config=self.config,
                neo4j_uri=os.getenv("NEO4J_URI"),
                neo4j_user=os.getenv("NEO4J_USERNAME"),
                neo4j_password=os.getenv("NEO4J_PASSWORD"),
                community_level=2,
                dynamic_community_selection=False,
                response_type=response_type,
                query=query,
                user_email=user_email
            )
            
            return {
                "response": response,
                "context_data": context_data,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error in global search: {e}")
            return {
                "response": "",
                "context_data": {},
                "success": False,
                "error": str(e)
            }
    
    async def local_search(self, query: str, response_type: str = "Multiple Paragraphs", user_email: str = None) -> Dict[str, Any]:
        """Perform local search using Neo4j"""
        try:
            result = await neo4j_local_search(
                config=self.config,
                query=query,
                response_type=response_type,
                user_email=user_email
            )
            return result
        except Exception as e:
            logger.error(f"Local search failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        
    def run_cypher_query(self, query: str) -> list[dict]:
        """Run a Cypher query against the Neo4j database."""
        
        with GraphDatabase.driver(
            os.getenv("NEO4J_URI"), 
            auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
        ).session() as session:
            result = session.run(query, user_email="system@example.com")
            
            # Extract data from the result object, similar to neo4j_local_context.py
            records = []
            for record in result:
                # Convert each record to a dictionary with all its fields
                record_dict = {}
                for key in record.keys():
                    record_dict[key] = record[key]
                records.append(record_dict)
            
            return records
                
    def get_top_k_documents(self, query: str, k: int = 5, document_type: str | None = None) -> list[str]:
        """Get the top k documents from Neo4j database."""
        if not self.neo4j_local_context:
            raise ValueError("Neo4j local context not initialized")
        return self.neo4j_local_context.get_top_k_documents(query, k=k, document_type=document_type)

    