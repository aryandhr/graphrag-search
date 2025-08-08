from fastapi import FastAPI, HTTPException, Depends
from service.unstructured import UnstructuredService
import uvicorn
from datetime import datetime
from dotenv import load_dotenv
import os
import logging
from contextlib import asynccontextmanager
from auth.security import get_current_user

from _types.query_types import QueryRequest
from auth.security import UserData
from agents.search_agent import SearchAgent
from service.structured import StructuredService
from service.connection import StructuredDataConnection

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

unstructured_search_service = None
structured_search_service = None
async def startup_event():
    """Runs when the FastAPI application starts up"""
    global unstructured_search_service, structured_search_service
    
    logger.info("🚀 Starting GraphRAG Web Service...")
    
    if not os.getenv("NEO4J_URI"):
        logger.error("❌ NEO4J_URI environment variable is not set")
        raise ValueError("NEO4J_URI environment variable is required")
    
    if not os.getenv("NEO4J_DATABASE"):
        logger.error("❌ NEO4J_DATABASE environment variable is not set")
        raise ValueError("NEO4J_DATABASE environment variable is required")
    
    try:
        unstructured_search_service = UnstructuredService()
        connection = StructuredDataConnection()
        connection.connect()
        structured_search_service = StructuredService(connection)
        
        logger.info("🔧 Initializing unstructured search...")
        schema_result = unstructured_search_service.initialize_schema()
        
        if schema_result.get("success"):    
            logger.info("✅ Unstructured search initialized")
        else:
            logger.warning(f"⚠️ Unstructured search initialization warning: {schema_result.get('error')}")

        structured_init_success = structured_search_service.initialize_structured_search()
        if structured_init_success:
            logger.info("✅ Structured search initialized")
        else:
            logger.error("❌ Structured search initialization failed")
            raise Exception("Structured search initialization failed")
        
        logger.info("🎉 GraphRAG Web Service started successfully!")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize GraphRAG service: {e}")
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_event()
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global unstructured_search_service, structured_search_service
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "neo4j_uri": os.getenv("NEO4J_URI"),
        "neo4j_database": os.getenv("NEO4J_DATABASE"),
        "service_initialized": unstructured_search_service is not None
    }
    
    if unstructured_search_service:
        try:
            connection_test = unstructured_search_service.test_connection()
            health_status["database_connected"] = connection_test.get("success", False)
            if not connection_test.get("success"):
                health_status["status"] = "unhealthy"
                health_status["database_error"] = connection_test.get("error")
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["database_error"] = str(e)
    else:
        health_status["status"] = "unhealthy"
        health_status["error"] = "Service not initialized"
    
    return health_status

@app.post("/query")
async def query_knowledge_graph(
    request: QueryRequest,
):
    """Query the knowledge graph with support for multiple search types"""
    global unstructured_search_service, structured_search_service
    
    if not unstructured_search_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not structured_search_service:
        raise HTTPException(status_code=503, detail="Structured search service not initialized")
    
    try:
        return await SearchAgent(request.query, unstructured_search_service, structured_search_service, request.email).run()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in query endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    print("Starting GraphRAG Web Server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)