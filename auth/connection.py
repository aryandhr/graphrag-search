from neo4j import GraphDatabase
from typing import Dict, Any
import logging
from dotenv import load_dotenv
import os

if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

logger = logging.getLogger(__name__)

def test_connection() -> Dict[str, Any]:
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_username = os.getenv("NEO4J_USERNAME")
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    neo4j_database = os.getenv("NEO4J_DATABASE")
    
    if not neo4j_uri:
        return {
            "success": False,
            "error": "NEO4J_URI environment variable is not set"
        }
    
    if not neo4j_username:
        return {
            "success": False,
            "error": "NEO4J_USERNAME environment variable is not set"
        }
    
    if not neo4j_password:
        return {
            "success": False,
            "error": "NEO4J_PASSWORD environment variable is not set"
        }
    
    if not neo4j_database:
        return {
            "success": False,
            "error": "NEO4J_DATABASE environment variable is not set"
        }
    
    driver = None
    try:
        logger.info(f"Testing connection to Neo4j at {neo4j_uri}")
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_username, neo4j_password))
        
        with driver.session(database=neo4j_database) as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            
            if record and record["test"] == 1:
                logger.info("✅ Neo4j connection test successful")
                return {
                    "success": True,
                    "message": "Database connection successful",
                    "uri": neo4j_uri,
                    "database": neo4j_database
                }
            else:
                return {
                    "success": False,
                    "error": "Connection test query failed"
                }
                
    except Exception as e:
        error_msg = f"Failed to connect to Neo4j: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return {
            "success": False,
            "error": error_msg
        }
    finally:
        if driver:
            driver.close()
            logger.debug("Neo4j driver connection closed")
