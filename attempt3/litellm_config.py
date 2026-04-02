"""
LiteLLM configuration and load balancing management
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import structlog

from litellm import Router
from litellm.types.utils import ModelResponse
from database import ModelServer, get_analytics_db, db_manager
from config import settings

logger = structlog.get_logger()


class LiteLLMManager:
    """Manages LiteLLM configuration and load balancing"""
    
    def __init__(self):
        self.router = None
        self.last_config_update = None
        self.config_update_interval = timedelta(minutes=5)  # Update config every 5 minutes
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize LiteLLM router with current configuration"""
        await self.update_router_config()
        
        # Start background task to periodically update configuration
        asyncio.create_task(self._periodic_config_update())
    
    async def get_model_list(self) -> List[Dict[str, Any]]:
        """Get model list from database for LiteLLM configuration"""
        async with db_manager.get_analytics_session() as session:
            result = await session.execute(
                select(ModelServer).where(ModelServer.is_active == True)
            )
            servers = result.scalars().all()
            
            model_list = []
            for server in servers:
                for model in server.models:
                    model_config = {
                        "model_name": model,
                        "litellm_params": {
                            "model": f"openai/{model}",
                            "api_base": f"{server.endpoint}/v1",
                            "api_key": "dummy-key",  # Your servers might not need auth
                            "weight": server.weight or 1
                        },
                        "model_info": {
                            "id": model,
                            "object": "model",
                            "created": int(datetime.utcnow().timestamp()),
                            "owned_by": server.name
                        }
                    }
                    model_list.append(model_config)
            
            logger.info("Generated model list", models=len(model_list), servers=len(servers))
            return model_list
    
    async def update_router_config(self):
        """Update LiteLLM router with latest configuration"""
        async with self._lock:
            try:
                model_list = await self.get_model_list()
                
                # Create new router with updated configuration
                new_router = Router(
                    model_list=model_list,
                    set_verbose=settings.litellm_debug,
                    debug=settings.litellm_debug,
                    load_balancing_strategy=settings.litellm_load_balancing_strategy
                )
                
                # Replace the old router
                old_router = self.router
                self.router = new_router
                self.last_config_update = datetime.utcnow()
                
                logger.info("LiteLLM router configuration updated", models=len(model_list))
                
                # Clean up old router if it existed
                if old_router:
                    try:
                        # LiteLLM doesn't have explicit cleanup, but we can clear caches
                        if hasattr(old_router, 'reset_cache'):
                            old_router.reset_cache()
                    except Exception as e:
                        logger.warning("Error cleaning up old router", error=str(e))
                
            except Exception as e:
                logger.error("Failed to update LiteLLM configuration", error=str(e))
                raise
    
    async def _periodic_config_update(self):
        """Background task to periodically update configuration"""
        while True:
            try:
                await asyncio.sleep(self.config_update_interval.total_seconds())
                await self.update_router_config()
            except Exception as e:
                logger.error("Error in periodic config update", error=str(e))
                # Continue running even if update fails
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from LiteLLM router"""
        if not self.router:
            await self.initialize()
        
        try:
            # Get models from router
            models = []
            model_list = self.router.model_list
            
            # Extract unique models
            seen_models = set()
            for model_config in model_list:
                model_name = model_config.get("model_name")
                if model_name and model_name not in seen_models:
                    models.append(model_config.get("model_info", {
                        "id": model_name,
                        "object": "model",
                        "created": int(datetime.utcnow().timestamp()),
                        "owned_by": "lite-llm-service"
                    }))
                    seen_models.add(model_name)
            
            return models
            
        except Exception as e:
            logger.error("Error getting available models", error=str(e))
            return []
    
    async def completion(self, **kwargs) -> ModelResponse:
        """Make a completion request using LiteLLM router"""
        if not self.router:
            await self.initialize()
        
        try:
            # Log the request
            model = kwargs.get("model", "unknown")
            logger.info("Completion request", model=model, stream=kwargs.get("stream", False))
            
            # Make the request through LiteLLM
            response = await self.router.acompletion(**kwargs)
            
            # Log successful response
            logger.info("Completion successful", 
                       model=model, 
                       tokens_used=getattr(response, 'usage', {}).get('total_tokens', 0))
            
            return response
            
        except Exception as e:
            logger.error("Completion request failed", model=model, error=str(e))
            raise
    
    async def register_server(
        self,
        name: str,
        endpoint: str,
        models: List[str],
        weight: int = 1,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """Register a new model server"""
        
        if not db:
            db = db_manager.get_analytics_session()
            async_with_db = False
        else:
            async_with_db = True
        
        try:
            if not async_with_db:
                await db.__aenter__()
            
            # Check if server already exists
            result = await db.execute(
                select(ModelServer).where(
                    (ModelServer.name == name) | (ModelServer.endpoint == endpoint)
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                raise ValueError(f"Server with name '{name}' or endpoint '{endpoint}' already exists")
            
            # Create new server
            new_server = ModelServer(
                name=name,
                endpoint=endpoint,
                models=models,
                weight=weight,
                health_score=1.0
            )
            
            db.add(new_server)
            await db.commit()
            await db.refresh(new_server)
            
            logger.info("Model server registered", 
                       server_id=str(new_server.id), 
                       name=name, 
                       endpoint=endpoint,
                       models=models)
            
            # Update router configuration
            await self.update_router_config()
            
            return {
                "id": str(new_server.id),
                "name": name,
                "endpoint": endpoint,
                "models": models,
                "weight": weight,
                "created_at": new_server.created_at
            }
            
        finally:
            if not async_with_db:
                await db.__aexit__(None, None, None)
    
    async def update_server_health(self, server_id: str, health_score: float):
        """Update server health score"""
        async with db_manager.get_analytics_session() as db:
            await db.execute(
                update(ModelServer)
                .where(ModelServer.id == server_id)
                .values(
                    health_score=health_score,
                    last_health_check=datetime.utcnow()
                )
            )
            await db.commit()
            
            logger.info("Server health updated", server_id=server_id, health_score=health_score)
    
    async def get_server_status(self) -> List[Dict[str, Any]]:
        """Get status of all servers"""
        async with db_manager.get_analytics_session() as db:
            result = await db.execute(
                select(ModelServer).where(ModelServer.is_active == True)
            )
            servers = result.scalars().all()
            
            return [
                {
                    "id": str(server.id),
                    "name": server.name,
                    "endpoint": server.endpoint,
                    "models": server.models,
                    "weight": server.weight,
                    "health_score": float(server.health_score),
                    "last_health_check": server.last_health_check.isoformat() if server.last_health_check else None,
                    "created_at": server.created_at.isoformat()
                }
                for server in servers
            ]
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all servers"""
        servers = await self.get_server_status()
        healthy_servers = []
        unhealthy_servers = []
        
        for server in servers:
            # Simple health check - in production, implement actual ping/health endpoint
            try:
                # For now, assume servers with health_score > 0.5 are healthy
                if server["health_score"] > 0.5:
                    healthy_servers.append(server)
                else:
                    unhealthy_servers.append(server)
            except Exception:
                unhealthy_servers.append(server)
        
        health_status = {
            "overall_healthy": len(unhealthy_servers) == 0,
            "total_servers": len(servers),
            "healthy_servers": len(healthy_servers),
            "unhealthy_servers": len(unhealthy_servers),
            "last_check": datetime.utcnow().isoformat(),
            "servers": servers
        }
        
        logger.info("Health check completed", **health_status)
        
        return health_status


# Global LiteLLM manager instance
litellm_manager = LiteLLMManager()
