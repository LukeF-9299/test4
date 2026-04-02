"""
Admin API endpoints for managing Lite LLM API Service
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, Depends, Query
from pydantic import BaseModel, Field
import structlog

from auth import APIKeyManager, require_api_key, APIKey
from litellm_config import litellm_manager
from database import APIKey, ModelServer, APICall, DailyUsage, HourlyMetrics
from database import get_api_keys_db, get_analytics_db, get_usage_logs_db, db_manager
from config import settings

logger = structlog.get_logger()


# Pydantic models for admin requests
class CreateAPIKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    expires_in_days: Optional[int] = Field(default=365, ge=1, le=3650)


class RegisterServerRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    endpoint: str = Field(..., min_length=1)
    models: List[str] = Field(..., min_items=1)
    weight: Optional[int] = Field(default=1, ge=1, le=100)


class UpdateServerRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    endpoint: Optional[str] = Field(None, min_length=1)
    models: Optional[List[str]] = Field(None, min_items=1)
    weight: Optional[int] = Field(None, ge=1, le=100)
    is_active: Optional[bool] = None


class UsageStatsRequest(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    model: Optional[str] = None
    api_key_id: Optional[str] = None


# API Key Management Endpoints

async def create_api_key_handler(
    request: CreateAPIKeyRequest,
    api_key: APIKey = Depends(require_api_key),
    db = Depends(get_api_keys_db)
) -> Dict[str, Any]:
    """Create a new API key"""
    
    try:
        new_key = await APIKeyManager.create_api_key(
            name=request.name,
            expires_in_days=request.expires_in_days,
            db=db
        )
        
        logger.info("API key created by admin", 
                   admin_key_id=str(api_key.id),
                   new_key_id=new_key["id"],
                   new_key_name=new_key["name"])
        
        return {
            "id": new_key["id"],
            "api_key": new_key["api_key"],
            "name": new_key["name"],
            "created_at": new_key["created_at"].isoformat(),
            "expires_at": new_key["expires_at"].isoformat() if new_key["expires_at"] else None
        }
        
    except Exception as e:
        logger.error("Failed to create API key", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create API key")


async def list_api_keys_handler(
    api_key: APIKey = Depends(require_api_key),
    db = Depends(get_api_keys_db)
) -> Dict[str, Any]:
    """List all API keys"""
    
    try:
        from sqlalchemy import select
        
        result = await db.execute(select(APIKey))
        keys = result.scalars().all()
        
        key_list = []
        for key in keys:
            key_data = {
                "id": str(key.id),
                "name": key.name,
                "created_at": key.created_at.isoformat(),
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                "is_active": key.is_active,
                "last_used": key.last_used.isoformat() if key.last_used else None,
                "usage_count": key.usage_count
            }
            key_list.append(key_data)
        
        logger.info("API keys listed", count=len(key_list), admin_key_id=str(api_key.id))
        
        return {"api_keys": key_list, "count": len(key_list)}
        
    except Exception as e:
        logger.error("Failed to list API keys", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list API keys")


async def rotate_api_key_handler(
    key_id: str,
    api_key: APIKey = Depends(require_api_key),
    db = Depends(get_api_keys_db)
) -> Dict[str, Any]:
    """Rotate an existing API key"""
    
    try:
        rotated_key = await APIKeyManager.rotate_api_key(key_id, db)
        
        logger.info("API key rotated by admin", 
                   admin_key_id=str(api_key.id),
                   rotated_key_id=key_id,
                   rotated_key_name=rotated_key["name"])
        
        return {
            "id": rotated_key["id"],
            "api_key": rotated_key["api_key"],
            "name": rotated_key["name"],
            "rotated_at": rotated_key["rotated_at"].isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to rotate API key", key_id=key_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to rotate API key")


async def revoke_api_key_handler(
    key_id: str,
    api_key: APIKey = Depends(require_api_key),
    db = Depends(get_api_keys_db)
) -> Dict[str, Any]:
    """Revoke an API key"""
    
    try:
        await APIKeyManager.revoke_api_key(key_id, db)
        
        logger.info("API key revoked by admin", 
                   admin_key_id=str(api_key.id),
                   revoked_key_id=key_id)
        
        return {"message": "API key revoked successfully", "id": key_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to revoke API key", key_id=key_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to revoke API key")


# Server Management Endpoints

async def register_server_handler(
    request: RegisterServerRequest,
    api_key: APIKey = Depends(require_api_key),
    db = Depends(get_analytics_db)
) -> Dict[str, Any]:
    """Register a new model server"""
    
    try:
        server = await litellm_manager.register_server(
            name=request.name,
            endpoint=request.endpoint,
            models=request.models,
            weight=request.weight,
            db=db
        )
        
        logger.info("Model server registered by admin", 
                   admin_key_id=str(api_key.id),
                   server_id=server["id"],
                   server_name=server["name"])
        
        return server
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to register server", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to register server")


async def list_servers_handler(
    api_key: APIKey = Depends(require_api_key)
) -> Dict[str, Any]:
    """List all model servers"""
    
    try:
        servers = await litellm_manager.get_server_status()
        
        logger.info("Model servers listed", 
                   count=len(servers), 
                   admin_key_id=str(api_key.id))
        
        return {"servers": servers, "count": len(servers)}
        
    except Exception as e:
        logger.error("Failed to list servers", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list servers")


async def update_server_handler(
    server_id: str,
    request: UpdateServerRequest,
    api_key: APIKey = Depends(require_api_key),
    db = Depends(get_analytics_db)
) -> Dict[str, Any]:
    """Update a model server"""
    
    try:
        from sqlalchemy import select, update
        
        # Check if server exists
        result = await db.execute(select(ModelServer).where(ModelServer.id == server_id))
        server = result.scalar_one_or_none()
        
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        
        # Update fields
        update_data = {}
        if request.name is not None:
            update_data["name"] = request.name
        if request.endpoint is not None:
            update_data["endpoint"] = request.endpoint
        if request.models is not None:
            update_data["models"] = request.models
        if request.weight is not None:
            update_data["weight"] = request.weight
        if request.is_active is not None:
            update_data["is_active"] = request.is_active
        
        update_data["updated_at"] = datetime.utcnow()
        
        await db.execute(
            update(ModelServer).where(ModelServer.id == server_id).values(**update_data)
        )
        await db.commit()
        
        # Update LiteLLM configuration
        await litellm_manager.update_router_config()
        
        logger.info("Model server updated by admin", 
                   admin_key_id=str(api_key.id),
                   server_id=server_id,
                   updated_fields=list(update_data.keys()))
        
        return {"message": "Server updated successfully", "id": server_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update server", server_id=server_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update server")


async def delete_server_handler(
    server_id: str,
    api_key: APIKey = Depends(require_api_key),
    db = Depends(get_analytics_db)
) -> Dict[str, Any]:
    """Delete a model server"""
    
    try:
        from sqlalchemy import delete
        
        # Check if server exists
        result = await db.execute(select(ModelServer).where(ModelServer.id == server_id))
        server = result.scalar_one_or_none()
        
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        
        # Delete server
        await db.execute(delete(ModelServer).where(ModelServer.id == server_id))
        await db.commit()
        
        # Update LiteLLM configuration
        await litellm_manager.update_router_config()
        
        logger.info("Model server deleted by admin", 
                   admin_key_id=str(api_key.id),
                   server_id=server_id,
                   server_name=server.name)
        
        return {"message": "Server deleted successfully", "id": server_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete server", server_id=server_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete server")


# Analytics and Monitoring Endpoints

async def get_usage_stats_handler(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    model: Optional[str] = Query(None),
    api_key_id: Optional[str] = Query(None),
    api_key: APIKey = Depends(require_api_key),
    db = Depends(get_usage_logs_db)
) -> Dict[str, Any]:
    """Get usage statistics"""
    
    try:
        from sqlalchemy import select, func
        
        # Set default date range (last 7 days)
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=7)
        
        # Build query
        query = select(
            func.count(APICall.id).label('total_requests'),
            func.sum(APICall.total_tokens).label('total_tokens'),
            func.avg(APICall.response_time_ms).label('avg_response_time'),
            func.count(func.nullif(APICall.status_code, 200)).label('error_count')
        ).where(
            APICall.timestamp >= start_date,
            APICall.timestamp <= end_date
        )
        
        # Add filters
        if model:
            query = query.where(APICall.model == model)
        if api_key_id:
            query = query.where(APICall.api_key_id == api_key_id)
        
        result = await db.execute(query)
        stats = result.first()
        
        # Calculate error rate
        total_requests = stats.total_requests or 0
        error_count = stats.error_count or 0
        error_rate = (error_count / total_requests) if total_requests > 0 else 0
        
        usage_stats = {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "total_requests": total_requests,
            "total_tokens": int(stats.total_tokens or 0),
            "avg_response_time_ms": float(stats.avg_response_time or 0),
            "error_count": error_count,
            "error_rate": error_rate,
            "filters": {
                "model": model,
                "api_key_id": api_key_id
            }
        }
        
        logger.info("Usage stats retrieved", 
                   admin_key_id=str(api_key.id),
                   period=f"{start_date.date()} to {end_date.date()}",
                   total_requests=total_requests)
        
        return usage_stats
        
    except Exception as e:
        logger.error("Failed to get usage stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get usage statistics")


async def get_health_status_handler(
    api_key: APIKey = Depends(require_api_key)
) -> Dict[str, Any]:
    """Get system health status"""
    
    try:
        # Get LiteLLM health status
        litellm_health = await litellm_manager.health_check()
        
        # Get database connection status
        db_status = {"api_keys": "healthy", "usage_logs": "healthy", "analytics": "healthy"}
        
        try:
            # Test database connections
            async with db_manager.get_api_keys_session() as db:
                await db.execute("SELECT 1")
        except Exception:
            db_status["api_keys"] = "unhealthy"
        
        try:
            async with db_manager.get_usage_logs_session() as db:
                await db.execute("SELECT 1")
        except Exception:
            db_status["usage_logs"] = "unhealthy"
        
        try:
            async with db_manager.get_analytics_session() as db:
                await db.execute("SELECT 1")
        except Exception:
            db_status["analytics"] = "unhealthy"
        
        overall_healthy = (
            litellm_health["overall_healthy"] and
            all(status == "healthy" for status in db_status.values())
        )
        
        health_status = {
            "overall_healthy": overall_healthy,
            "timestamp": datetime.utcnow().isoformat(),
            "litellm": litellm_health,
            "databases": db_status,
            "uptime": "N/A"  # Could be tracked if needed
        }
        
        logger.info("Health status retrieved", 
                   admin_key_id=str(api_key.id),
                   overall_healthy=overall_healthy)
        
        return health_status
        
    except Exception as e:
        logger.error("Failed to get health status", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get health status")


async def get_dashboard_data_handler(
    api_key: APIKey = Depends(require_api_key)
) -> Dict[str, Any]:
    """Get data for admin dashboard"""
    
    try:
        # Get recent usage stats (last 24 hours)
        from sqlalchemy import select, func
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        
        async with db_manager.get_usage_logs_session() as usage_db:
            # Recent requests
            recent_requests_query = select(func.count(APICall.id)).where(
                APICall.timestamp >= start_time
            )
            recent_requests_result = await usage_db.execute(recent_requests_query)
            recent_requests = recent_requests_result.scalar() or 0
            
            # Top models
            top_models_query = select(
                APICall.model,
                func.count(APICall.id).label('request_count')
            ).where(
                APICall.timestamp >= start_time
            ).group_by(APICall.model).order_by(
                func.count(APICall.id).desc()
            ).limit(10)
            
            top_models_result = await usage_db.execute(top_models_query)
            top_models = [
                {"model": row.model, "count": row.request_count}
                for row in top_models_result
            ]
        
        # Get server status
        servers = await litellm_manager.get_server_status()
        
        # Get API key count
        async with db_manager.get_api_keys_session() as keys_db:
            from sqlalchemy import select, func
            active_keys_query = select(func.count(APIKey.id)).where(APIKey.is_active == True)
            active_keys_result = await keys_db.execute(active_keys_query)
            active_keys = active_keys_result.scalar() or 0
        
        dashboard_data = {
            "summary": {
                "recent_requests_24h": recent_requests,
                "active_servers": len([s for s in servers if s["health_score"] > 0.5]),
                "total_servers": len(servers),
                "active_api_keys": active_keys
            },
            "servers": servers,
            "top_models": top_models,
            "last_updated": datetime.utcnow().isoformat()
        }
        
        logger.info("Dashboard data retrieved", admin_key_id=str(api_key.id))
        
        return dashboard_data
        
    except Exception as e:
        logger.error("Failed to get dashboard data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get dashboard data")
