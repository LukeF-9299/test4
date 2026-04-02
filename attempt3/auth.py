"""
Authentication middleware and utilities for Lite LLM API Service
"""

import bcrypt
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import structlog

from database import APIKey, get_api_keys_db
from config import settings

logger = structlog.get_logger()

# Security scheme for FastAPI
security = HTTPBearer(auto_error=False)


class APIKeyManager:
    """Manages API key creation, validation, and rotation"""
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a new API key"""
        return f"sk-{uuid.uuid4().hex}"
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash an API key for storage"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(api_key.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_api_key_hash(api_key: str, hashed_key: str) -> bool:
        """Verify an API key against its hash"""
        try:
            return bcrypt.checkpw(api_key.encode('utf-8'), hashed_key.encode('utf-8'))
        except Exception as e:
            logger.error("API key verification failed", error=str(e))
            return False
    
    @staticmethod
    async def create_api_key(
        name: str,
        expires_in_days: Optional[int] = 365,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """Create a new API key"""
        if not db:
            raise ValueError("Database session required")
        
        # Generate API key and hash
        api_key = APIKeyManager.generate_api_key()
        key_hash = APIKeyManager.hash_api_key(api_key)
        
        # Calculate expiry
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Save to database
        new_key = APIKey(
            key_hash=key_hash,
            name=name,
            expires_at=expires_at
        )
        
        db.add(new_key)
        await db.commit()
        await db.refresh(new_key)
        
        logger.info("API key created", key_id=str(new_key.id), name=name)
        
        return {
            "id": str(new_key.id),
            "api_key": api_key,
            "name": name,
            "created_at": new_key.created_at,
            "expires_at": expires_at
        }
    
    @staticmethod
    async def rotate_api_key(
        key_id: str,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """Rotate an existing API key"""
        if not db:
            raise ValueError("Database session required")
        
        # Get existing key
        result = await db.execute(select(APIKey).where(APIKey.id == key_id))
        existing_key = result.scalar_one_or_none()
        
        if not existing_key:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Generate new key
        new_api_key = APIKeyManager.generate_api_key()
        new_key_hash = APIKeyManager.hash_api_key(new_api_key)
        
        # Store old hash for rotation tracking
        old_hash = existing_key.key_hash
        
        # Update the key
        existing_key.key_hash = new_key_hash
        await db.commit()
        
        logger.info("API key rotated", key_id=key_id)
        
        return {
            "id": str(existing_key.id),
            "api_key": new_api_key,
            "name": existing_key.name,
            "rotated_at": datetime.utcnow()
        }
    
    @staticmethod
    async def revoke_api_key(key_id: str, db: AsyncSession = None):
        """Revoke an API key"""
        if not db:
            raise ValueError("Database session required")
        
        result = await db.execute(
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(is_active=False)
        )
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="API key not found")
        
        await db.commit()
        logger.info("API key revoked", key_id=key_id)


class AuthenticationMiddleware:
    """Middleware for API key authentication"""
    
    @staticmethod
    async def get_current_api_key(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        db: AsyncSession = Depends(get_api_keys_db)
    ) -> APIKey:
        """Validate API key and return the API key object"""
        
        if not credentials:
            raise HTTPException(
                status_code=401,
                detail="API key required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Extract the key from Bearer token
        api_key = credentials.credentials
        
        # Get all active API keys and check against them
        result = await db.execute(
            select(APIKey).where(APIKey.is_active == True)
        )
        active_keys = result.scalars().all()
        
        # Find matching key
        api_key_obj = None
        for key in active_keys:
            if APIKeyManager.verify_api_key_hash(api_key, key.key_hash):
                api_key_obj = key
                break
        
        if not api_key_obj:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if key has expired
        if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=401,
                detail="API key expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Update last used and usage count
        await db.execute(
            update(APIKey)
            .where(APIKey.id == api_key_obj.id)
            .values(
                last_used=datetime.utcnow(),
                usage_count=APIKey.usage_count + 1
            )
        )
        await db.commit()
        
        logger.info("API key authenticated", key_id=str(api_key_obj.id), name=api_key_obj.name)
        
        return api_key_obj
    
    @staticmethod
    async def get_optional_api_key(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        db: AsyncSession = Depends(get_api_keys_db)
    ) -> Optional[APIKey]:
        """Optional API key authentication for endpoints that don't require auth"""
        
        if not credentials:
            return None
        
        try:
            return await AuthenticationMiddleware.get_current_api_key(credentials, db)
        except HTTPException:
            return None


class RateLimiter:
    """Simple rate limiting for API keys"""
    
    def __init__(self):
        # In-memory storage for rate limits
        # In production, use Redis or similar
        self.requests = {}
    
    async def check_rate_limit(
        self,
        api_key_id: str,
        limit: int = 1000,  # requests per hour
        window: int = 3600   # 1 hour window
    ) -> bool:
        """Check if API key is within rate limits"""
        
        now = datetime.utcnow()
        key_requests = self.requests.get(api_key_id, [])
        
        # Remove old requests outside the window
        key_requests = [
            req_time for req_time in key_requests
            if (now - req_time).total_seconds() < window
        ]
        
        # Check if under limit
        if len(key_requests) >= limit:
            return False
        
        # Add current request
        key_requests.append(now)
        self.requests[api_key_id] = key_requests
        
        return True


# Global rate limiter instance
rate_limiter = RateLimiter()


async def require_api_key(api_key: APIKey = Depends(AuthenticationMiddleware.get_current_api_key)):
    """Dependency to require API key authentication"""
    return api_key


async def optional_api_key(api_key: Optional[APIKey] = Depends(AuthenticationMiddleware.get_optional_api_key)):
    """Dependency for optional API key authentication"""
    return api_key


# Request logging middleware
async def log_request(request: Request, api_key: Optional[APIKey] = None):
    """Log API request details"""
    
    log_data = {
        "method": request.method,
        "url": str(request.url),
        "timestamp": datetime.utcnow().isoformat(),
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
    
    if api_key:
        log_data["api_key_id"] = str(api_key.id)
        log_data["api_key_name"] = api_key.name
    
    logger.info("API request", **log_data)
