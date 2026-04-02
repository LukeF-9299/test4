"""
LiteLLM configuration management using file-based server configuration
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
import structlog

from litellm import Router
from litellm.types.utils import ModelResponse
from config import settings
from custom_api_adapters import custom_api_manager

logger = structlog.get_logger()


class FileBasedLiteLLMManager:
    """Manages LiteLLM configuration using file-based server configuration"""
    
    def __init__(self):
        self.router = None
        self.servers_config = None
        self.last_config_update = None
        self.config_update_interval = timedelta(minutes=5)
        self._lock = asyncio.Lock()
        self._config_file_path = Path(settings.servers_config_file)
        
    async def initialize(self):
        """Initialize LiteLLM router with configuration from file"""
        await self.load_config_from_file()
        await self.update_router_config()
        
        # Start background task to watch for config changes
        asyncio.create_task(self._config_file_watcher())
    
    async def load_config_from_file(self):
        """Load server configuration from JSON file"""
        try:
            self.servers_config = settings.load_servers_config()
            logger.info("Loaded server configuration from file", 
                       servers=len(self.servers_config.get("servers", [])))
        except Exception as e:
            logger.error("Failed to load server configuration", error=str(e))
            # Use default empty configuration
            self.servers_config = {
                "servers": [],
                "load_balancing": {
                    "strategy": "weighted",
                    "health_check_interval": 30,
                    "retry_attempts": 3
                },
                "api_keys": {}
            }
    
    async def save_config_to_file(self):
        """Save current configuration to file"""
        try:
            settings.save_servers_config(self.servers_config)
            logger.info("Saved server configuration to file")
        except Exception as e:
            logger.error("Failed to save server configuration", error=str(e))
    
    async def update_router_config(self):
        """Update LiteLLM router with latest configuration"""
        async with self._lock:
            try:
                model_list = self._build_model_list()
                
                if not model_list:
                    logger.warning("No servers configured - router will be empty")
                
                # Create new router with updated configuration
                new_router = Router(
                    model_list=model_list,
                    set_verbose=settings.litellm_debug,
                    debug=settings.litellm_debug,
                    load_balancing_strategy=self.servers_config.get("load_balancing", {}).get("strategy", "weighted")
                )
                
                # Replace the old router
                old_router = self.router
                self.router = new_router
                self.last_config_update = datetime.utcnow()
                
                logger.info("LiteLLM router configuration updated", 
                           models=len(model_list),
                           strategy=self.servers_config.get("load_balancing", {}).get("strategy"))
                
                # Clean up old router if it existed
                if old_router:
                    try:
                        if hasattr(old_router, 'reset_cache'):
                            old_router.reset_cache()
                    except Exception as e:
                        logger.warning("Error cleaning up old router", error=str(e))
                
            except Exception as e:
                logger.error("Failed to update LiteLLM configuration", error=str(e))
                raise
    
    def _build_model_list(self) -> List[Dict[str, Any]]:
        """Build LiteLLM model list from server configuration"""
        model_list = []
        api_keys = self.servers_config.get("api_keys", {})
        
        for server in self.servers_config.get("servers", []):
            server_name = server.get("name", "Unknown Server")
            endpoint = server.get("endpoint", "")
            models = server.get("models", [])
            weight = server.get("weight", 1)
            api_key_required = server.get("api_key_required", False)
            adapter_type = server.get("adapter_type", "openai")
            
            # Skip non-OpenAI compatible servers for LiteLLM router
            if adapter_type != "openai":
                logger.debug(f"Skipping non-OpenAI server for LiteLLM router: {server_name}")
                continue
            
            # Determine API key for this server
            api_key = "dummy-key"  # Default for servers that don't need auth
            if api_key_required:
                # Try to find appropriate API key based on server name/endpoint
                if "openai" in server_name.lower() or "openai" in endpoint.lower():
                    api_key = api_keys.get("openai", "your-openai-api-key")
                elif "anthropic" in server_name.lower() or "anthropic" in endpoint.lower():
                    api_key = api_keys.get("anthropic", "your-anthropic-api-key")
                elif "google" in server_name.lower() or "google" in endpoint.lower():
                    api_key = api_keys.get("google", "your-google-api-key")
                else:
                    api_key = api_keys.get("default", "dummy-key")
            
            for model in models:
                model_config = {
                    "model_name": model,
                    "litellm_params": {
                        "model": f"openai/{model}",  # Assume OpenAI-compatible format
                        "api_base": f"{endpoint}/v1",
                        "api_key": api_key,
                        "weight": weight
                    },
                    "model_info": {
                        "id": model,
                        "object": "model",
                        "created": int(datetime.utcnow().timestamp()),
                        "owned_by": server_name
                    }
                }
                model_list.append(model_config)
        
        return model_list
    
    async def _config_file_watcher(self):
        """Background task to watch for config file changes"""
        last_modified = None
        
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if self._config_file_path.exists():
                    current_modified = self._config_file_path.stat().st_mtime
                    
                    if last_modified is None:
                        last_modified = current_modified
                    elif current_modified > last_modified:
                        logger.info("Configuration file changed, reloading...")
                        await self.load_config_from_file()
                        await self.update_router_config()
                        last_modified = current_modified
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error watching config file", error=str(e))
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from configuration"""
        if not self.servers_config:
            await self.load_config_from_file()
        
        models = []
        seen_models = set()
        
        for server in self.servers_config.get("servers", []):
            for model in server.get("models", []):
                if model not in seen_models:
                    models.append({
                        "id": model,
                        "object": "model",
                        "created": int(datetime.utcnow().timestamp()),
                        "owned_by": server.get("name", "Unknown")
                    })
                    seen_models.add(model)
        
        return models
    
    async def completion(self, **kwargs) -> ModelResponse:
        """Make a completion request using LiteLLM router or custom adapters"""
        if not self.router:
            await self.initialize()
        
        model = kwargs.get("model", "unknown")
        logger.info("Completion request", model=model, stream=kwargs.get("stream", False))
        
        # First, try to find a server that can handle this model
        server_config = self._find_server_for_model(model)
        
        if server_config and server_config.get("adapter_type") != "openai":
            # Use custom adapter for non-OpenAI compatible servers
            try:
                response = await custom_api_manager.handle_request(server_config, kwargs)
                if response:
                    logger.info("Custom adapter completion successful", model=model)
                    return response
            except Exception as e:
                logger.error("Custom adapter failed", model=model, error=str(e))
                # Fall back to LiteLLM if custom adapter fails
        elif server_config and server_config.get("adapter_type") == "openai":
            # Use LiteLLM for OpenAI-compatible servers
            try:
                response = await self.router.acompletion(**kwargs)
                logger.info("LiteLLM completion successful", 
                           model=model, 
                           tokens_used=getattr(response, 'usage', {}).get('total_tokens', 0))
                return response
            except Exception as e:
                logger.error("LiteLLM completion failed", model=model, error=str(e))
                raise
        
        # If no specific server found or all failed, try LiteLLM as fallback
        try:
            response = await self.router.acompletion(**kwargs)
            logger.info("Fallback LiteLLM completion successful", model=model)
            return response
        except Exception as e:
            logger.error("All completion methods failed", model=model, error=str(e))
            raise
    
    def _find_server_for_model(self, model: str) -> Optional[Dict[str, Any]]:
        """Find server configuration for a specific model"""
        for server in self.servers_config.get("servers", []):
            if model in server.get("models", []):
                return server
        return None
    
    async def add_server(self, server_config: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new server to the configuration"""
        await self.load_config_from_file()
        
        # Check if server already exists
        existing_servers = self.servers_config.get("servers", [])
        for existing in existing_servers:
            if (existing.get("name") == server_config.get("name") or 
                existing.get("endpoint") == server_config.get("endpoint")):
                raise ValueError(f"Server with name '{server_config.get('name')}' or endpoint '{server_config.get('endpoint')}' already exists")
        
        # Add new server
        self.servers_config["servers"].append(server_config)
        await self.save_config_to_file()
        await self.update_router_config()
        
        logger.info("Server added to configuration", 
                   name=server_config.get("name"),
                   endpoint=server_config.get("endpoint"),
                   adapter_type=server_config.get("adapter_type"))
        
        return {"status": "success", "message": "Server added successfully"}
    
    async def remove_server(self, server_name: str) -> Dict[str, Any]:
        """Remove a server from the configuration"""
        await self.load_config_from_file()
        
        servers = self.servers_config.get("servers", [])
        original_count = len(servers)
        
        # Remove server by name
        self.servers_config["servers"] = [
            server for server in servers 
            if server.get("name") != server_name
        ]
        
        if len(self.servers_config["servers"]) == original_count:
            raise ValueError(f"Server '{server_name}' not found")
        
        await self.save_config_to_file()
        await self.update_router_config()
        
        logger.info("Server removed from configuration", name=server_name)
        
        return {"status": "success", "message": f"Server '{server_name}' removed successfully"}
    
    async def update_server(self, server_name: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a server in the configuration"""
        await self.load_config_from_file()
        
        servers = self.servers_config.get("servers", [])
        server_found = False
        
        for server in servers:
            if server.get("name") == server_name:
                server.update(updates)
                server_found = True
                break
        
        if not server_found:
            raise ValueError(f"Server '{server_name}' not found")
        
        await self.save_config_to_file()
        await self.update_router_config()
        
        logger.info("Server updated in configuration", 
                   name=server_name, 
                   updates=list(updates.keys()))
        
        return {"status": "success", "message": f"Server '{server_name}' updated successfully"}
    
    async def get_server_status(self) -> List[Dict[str, Any]]:
        """Get status of all configured servers"""
        if not self.servers_config:
            await self.load_config_from_file()
        
        servers = []
        for server in self.servers_config.get("servers", []):
            servers.append({
                "name": server.get("name"),
                "endpoint": server.get("endpoint"),
                "models": server.get("models", []),
                "weight": server.get("weight", 1),
                "api_key_required": server.get("api_key_required", False),
                "adapter_type": server.get("adapter_type", "openai"),
                "description": server.get("description", ""),
                "health_score": 1.0,  # Default health score
                "last_health_check": None,
                "is_active": True
            })
        
        return servers
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the system"""
        servers = await self.get_server_status()
        
        health_status = {
            "overall_healthy": len(servers) > 0,
            "total_servers": len(servers),
            "healthy_servers": len(servers),  # All servers assumed healthy in file-based mode
            "unhealthy_servers": 0,
            "last_check": datetime.utcnow().isoformat(),
            "servers": servers,
            "config_file": str(self._config_file_path),
            "config_last_updated": self.last_config_update.isoformat() if self.last_config_update else None
        }
        
        logger.info("Health check completed", **health_status)
        
        return health_status
    
    async def get_config_info(self) -> Dict[str, Any]:
        """Get current configuration information"""
        if not self.servers_config:
            await self.load_config_from_file()
        
        return {
            "config_file": str(self._config_file_path),
            "last_updated": self.last_config_update.isoformat() if self.last_config_update else None,
            "total_servers": len(self.servers_config.get("servers", [])),
            "load_balancing": self.servers_config.get("load_balancing", {}),
            "models": await self.get_available_models()
        }


# Global LiteLLM manager instance
litellm_manager = FileBasedLiteLLMManager()
