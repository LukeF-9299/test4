"""
Main FastAPI application for Lite LLM API Service
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import structlog

from config import settings
from database import db_manager, cleanup_old_data, create_indexes
from litellm_file_config import litellm_manager
from auth import log_request

# Import endpoint handlers
from api_endpoints import (
    chat_completions_handler,
    completions_handler,
    models_handler
)
from admin_endpoints import (
    create_api_key_handler,
    list_api_keys_handler,
    rotate_api_key_handler,
    revoke_api_key_handler,
    get_usage_stats_handler,
    get_health_status_handler,
    get_dashboard_data_handler
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    
    # Startup
    logger.info("Starting Lite LLM API Service...", 
               environment=settings.environment,
               db_type="SQLite (local)" if settings.use_local_db else "PostgreSQL")
    
    try:
        # Initialize database connections
        db_urls = settings.get_database_urls()
        await db_manager.initialize(db_urls)
        
        db_info = await db_manager.get_database_info()
        logger.info("Database connections initialized", **db_info)
        
        # Create performance indexes
        await create_indexes()
        logger.info("Database indexes created")
        
        # Initialize LiteLLM manager with file-based configuration
        await litellm_manager.initialize()
        logger.info("LiteLLM manager initialized with file-based configuration")
        
        # Start background tasks
        asyncio.create_task(background_cleanup_task())
        logger.info("Background tasks started")
        
        logger.info("Lite LLM API Service started successfully")
        
        yield
        
    except Exception as e:
        logger.error("Failed to start application", error=str(e))
        raise
    
    finally:
        # Shutdown
        logger.info("Shutting down Lite LLM API Service...")
        await db_manager.close()
        logger.info("Lite LLM API Service stopped")


# Create FastAPI application
app = FastAPI(
    title="Lite LLM API Service",
    description="Scalable API gateway for OpenAI-compatible model servers with file-based configuration",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint (no auth required)
@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    db_info = await db_manager.get_database_info()
    return {
        "status": "healthy",
        "timestamp": structlog.processors.TimeStamper().format_timestamp(None),
        "version": "1.0.0",
        "environment": settings.environment,
        "database": db_info
    }


# OpenAI-compatible API endpoints
@app.post("/v1/chat/completions")
async def chat_completions(request):
    """OpenAI-compatible chat completions endpoint"""
    return await chat_completions_handler(request)


@app.post("/v1/completions")
async def completions(request):
    """OpenAI-compatible completions endpoint"""
    return await completions_handler(request)


@app.get("/v1/models")
async def models():
    """List available models"""
    return await models_handler()


# Admin API endpoints
@app.post("/admin/api-keys")
async def create_api_key(request):
    """Create a new API key"""
    return await create_api_key_handler(request)


@app.get("/admin/api-keys")
async def list_api_keys():
    """List all API keys"""
    return await list_api_keys_handler()


@app.post("/admin/api-keys/{key_id}/rotate")
async def rotate_api_key(key_id: str):
    """Rotate an API key"""
    return await rotate_api_key_handler(key_id)


@app.delete("/admin/api-keys/{key_id}")
async def revoke_api_key(key_id: str):
    """Revoke an API key"""
    return await revoke_api_key_handler(key_id)


@app.get("/admin/servers")
async def list_servers():
    """List all configured servers"""
    return await litellm_manager.get_server_status()


@app.post("/admin/servers")
async def add_server(request):
    """Add a new server to configuration"""
    return await litellm_manager.add_server(request)


@app.put("/admin/servers/{server_name}")
async def update_server(server_name: str, request):
    """Update a server in configuration"""
    return await litellm_manager.update_server(server_name, request)


@app.delete("/admin/servers/{server_name}")
async def remove_server(server_name: str):
    """Remove a server from configuration"""
    return await litellm_manager.remove_server(server_name)


@app.get("/admin/config")
async def get_config():
    """Get current configuration"""
    return await litellm_manager.get_config_info()


@app.put("/admin/config")
async def update_config(request):
    """Update server configuration file"""
    return await litellm_manager.save_config_to_file(request)


@app.get("/admin/usage-stats")
async def get_usage_stats(
    start_date=None,
    end_date=None,
    model=None,
    api_key_id=None
):
    """Get usage statistics"""
    return await get_usage_stats_handler(
        start_date, end_date, model, api_key_id
    )


@app.get("/admin/health")
async def get_health_status():
    """Get system health status"""
    return await get_health_status_handler()


@app.get("/admin/dashboard")
async def get_dashboard_data():
    """Get admin dashboard data"""
    return await get_dashboard_data_handler()


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.warning("HTTP exception", 
                   status_code=exc.status_code, 
                   detail=exc.detail,
                   path=request.url.path)
    return {"error": {"message": exc.detail, "type": "http_error"}}


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error("Unhandled exception", 
                 error=str(exc), 
                 path=request.url.path,
                 exc_info=True)
    return {"error": {"message": "Internal server error", "type": "internal_error"}}


# Background tasks
async def background_cleanup_task():
    """Background task for data cleanup and maintenance"""
    
    while True:
        try:
            # Wait for 24 hours before running cleanup
            await asyncio.sleep(24 * 60 * 60)  # 24 hours
            
            logger.info("Running background cleanup task")
            
            # Clean up old data based on retention policy
            await cleanup_old_data(retention_days=settings.data_retention_days)
            
            logger.info("Background cleanup completed")
            
        except Exception as e:
            logger.error("Background cleanup failed", error=str(e))
            # Continue running even if cleanup fails


# Request logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    """Log all API requests"""
    
    start_time = structlog.processors.TimeStamper().format_timestamp(None)
    
    response = await call_next(request)
    
    end_time = structlog.processors.TimeStamper().format_timestamp(None)
    
    logger.info("API request",
               method=request.method,
               path=request.url.path,
               status_code=response.status_code,
               start_time=start_time,
               end_time=end_time,
               client_ip=request.client.host if request.client else None)
    
    return response


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower()
    )
