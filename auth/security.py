from fastapi import Depends, HTTPException, Body
from typing import Dict, Any, Optional, TypedDict
from neo4j import GraphDatabase
import os
import logging
from dotenv import load_dotenv

if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")

class UserData(TypedDict):
    """Type definition for user data returned from Neo4j"""
    id: str
    displayName: str
    email: str
    createdOn: str
    status: str
    hasGraph: bool

class UserAuthService:
    """Service for handling user authentication with Neo4j"""
    
    def __init__(self):
        self.driver = None
        self._initialize_driver()
    
    def _initialize_driver(self):
        """Initialize Neo4j driver connection"""
        if not all([NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE]):
            logger.error("Missing Neo4j environment variables for authentication")
            raise ValueError("Neo4j environment variables not properly configured")
        
        try:
            self.driver = GraphDatabase.driver(
                NEO4J_URI, 
                auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
            )
            logger.info("Neo4j authentication driver initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j driver: {e}")
            raise
    
    def get_user_by_email(self, email: str) -> Optional[UserData]:
        """Get user from Neo4j database by email"""
        if not self.driver:
            logger.error("Neo4j driver not initialized")
            return None
        
        try:
            with self.driver.session(database=NEO4J_DATABASE) as session:
                query = """
                MATCH (u:User {email: $email})
                RETURN u
                LIMIT 1
                """
                
                result = session.run(query, email=email)
                record = result.single()
                
                if record:
                    user_node = record["u"]
                    user_data = {
                        "id": str(user_node.id),
                        "displayName": user_node.get("displayName"),
                        "email": user_node.get("email"),
                        "createdOn": user_node.get("createdOn"),
                        "status": user_node.get("status"),
                        "hasGraph": bool(user_node.get("hasGraph"))
                    }
                    logger.info(f"Found user: {user_data['email']}")
                    return user_data
                else:
                    logger.warning(f"No user found with email: {email}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error querying user by email: {e}")
            return None
    
    def verify_user_status(self, user: UserData) -> bool:
        """Verify that the user has an active status"""
        if not user:
            return False
        
        status = user.get("status", "").lower()
        if status == "active":
            logger.info(f"User {user.get('email')} has active status")
            return True
        else:
            logger.warning(f"User {user.get('email')} has inactive status: {status}")
            return False
    
    def close(self):
        """Close the Neo4j driver connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j authentication driver closed")

# Global instance of the auth service
auth_service = UserAuthService()

def get_current_user(email: str = Body(..., embed=True)) -> UserData:
    """
    Get the current authenticated user from request body
    
    This function takes the email from the request body and looks up the user in the Neo4j database.
    """
    try:
        if not email or "@" not in email:
            raise HTTPException(
                status_code=401, 
                detail="Invalid email format"
            )
        
        user = auth_service.get_user_by_email(email)
        
        if not user:
            raise HTTPException(
                status_code=401, 
                detail="User not found in database"
            )
        
        if not auth_service.verify_user_status(user):
            raise HTTPException(
                status_code=401, 
                detail="User account is not active"
            )
        
        logger.info(f"Successfully authenticated user: {user['email']}")
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Internal authentication error"
        )
