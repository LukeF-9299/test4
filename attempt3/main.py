"""
Lite LLM API Service
A scalable API gateway for OpenAI-compatible model servers with load balancing
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
import uuid
import bcrypt
import json
from datetime import datetime, timedelta

# LiteLLM imports
from litellm import completion, acompletion, get_supported_openai_params
from litellm.integrations.fastapi import FastAILitellmRouter
from litellm.types.utils import ModelResponse

# Database imports
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, BigInteger, DECIMAL, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import sqlalchemy as sa

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

# Database Models
class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    key_hash = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime, nullable=True)
    usage_count = Column(BigInteger, default=0)

class APICall(Base):
    __tablename__ = "api_calls"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    api_key_id = Column(UUID(as_uuid=True), nullable=True)
    model = Column(String(255), nullable=False)
    server_endpoint = Column(String(255), nullable=False)
    request_tokens = Column(Integer, nullable=True)
    response_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    request_id = Column(String(255), unique=True)

class ModelServer(Base):
    __tablename__ = "model_servers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    name = Column(String(255), nullable=False)
    endpoint = Column(String(255), nullable=False)
    models = Column(sa.JSON, nullable=False)  # Array of available models
    is_active = Column(Boolean, default=True)
    weight = Column(Integer, default=1)
    last_health_check = Column(DateTime, nullable=True)
    health_score = Column(DECIMAL(3,2), default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

# Global variables
app = FastAPI(title="Lite LLM API Service", version="1.0.0")
engine = None
SessionLocal = None
litellm_router = None

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global engine, SessionLocal, litellm_router
    
    # Initialize database
    engine = create_async_engine(
        "postgresql+asyncpg://user:password@localhost/api_keys_db",
        echo=True
    )
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize LiteLLM router with model configuration
    litellm_router = FastAILitellmRouter(
        model_list=[
            # This will be populated from database
        ],
        set_verbose=True,
        debug=True
    )
    
    logger.info("Lite LLM API Service started successfully")
    
    yield
    
    # Shutdown
    await engine.dispose()
    logger.info("Lite LLM API Service stopped")

app.router.lifespan_context = lifespan

# Database dependency
async def get_db():
    async with SessionLocal() as session:
        yield session

# API Key Authentication
async def verify_api_key(request: Request, db: AsyncSession = Depends(get_db)) -> APIKey:
    api_key = request.headers.get("Authorization")
    if not api_key or not api_key.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    
    api_key = api_key.replace("Bearer ", "")
    key_hash = bcrypt.hashpw(api_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Query API key from database
    result = await db.execute(
        sa.select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active == True)
    )
    api_key_obj = result.scalar_one_or_none()
    
    if not api_key_obj:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Update last used and usage count
    api_key_obj.last_used = datetime.utcnow()
    api_key_obj.usage_count += 1
    await db.commit()
    
    return api_key_obj

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# Models endpoint
@app.get("/v1/models")
async def list_models(api_key: APIKey = Depends(verify_api_key)):
    try:
        # Get models from LiteLLM router
        models = await litellm_router.get_models()
        return {"object": "list", "data": models}
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail="Failed to list models")

# Chat completions endpoint
@app.post("/v1/chat/completions")
async def chat_completions(
    request: Dict[str, Any],
    api_key: APIKey = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    request_id = str(uuid.uuid4())
    start_time = datetime.utcnow()
    
    try:
        # Log the request
        api_call = APICall(
            api_key_id=api_key.id,
            model=request.get("model", "unknown"),
            server_endpoint="unknown",  # Will be updated by LiteLLM
            request_id=request_id,
            timestamp=start_time
        )
        db.add(api_call)
        await db.commit()
        
        # Handle streaming
        stream = request.get("stream", False)
        
        if stream:
            return await handle_streaming_completion(request, request_id, api_call.id, db, start_time)
        else:
            return await handle_regular_completion(request, request_id, api_call.id, db, start_time)
            
    except Exception as e:
        logger.error(f"Error in chat completion: {e}")
        # Update API call with error
        await db.execute(
            sa.update(APICall)
            .where(APICall.request_id == request_id)
            .values(
                status_code=500,
                error_message=str(e),
                response_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
            )
        )
        await db.commit()
        raise HTTPException(status_code=500, detail="Internal server error")

async def handle_regular_completion(request: Dict[str, Any], request_id: str, api_call_id: str, db: AsyncSession, start_time: datetime):
    try:
        response = await acompletion(**request)
        
        # Calculate tokens and timing
        end_time = datetime.utcnow()
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Update API call with response data
        await db.execute(
            sa.update(APICall)
            .where(APICall.id == api_call_id)
            .values(
                request_tokens=response.get("usage", {}).get("prompt_tokens"),
                response_tokens=response.get("usage", {}).get("completion_tokens"),
                total_tokens=response.get("usage", {}).get("total_tokens"),
                response_time_ms=response_time_ms,
                status_code=200
            )
        )
        await db.commit()
        
        return response
        
    except Exception as e:
        end_time = datetime.utcnow()
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        await db.execute(
            sa.update(APICall)
            .where(APICall.id == api_call_id)
            .values(
                status_code=500,
                error_message=str(e),
                response_time_ms=response_time_ms
            )
        )
        await db.commit()
        raise

async def handle_streaming_completion(request: Dict[str, Any], request_id: str, api_call_id: str, db: AsyncSession, start_time: datetime):
    async def generate():
        try:
            response = await acompletion(**request)
            
            async for chunk in response:
                yield f"data: {json.dumps(chunk)}\n\n"
            
            # Final update for streaming
            end_time = datetime.utcnow()
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            await db.execute(
                sa.update(APICall)
                .where(APICall.id == api_call_id)
                .values(
                    response_time_ms=response_time_ms,
                    status_code=200
                )
            )
            await db.commit()
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            end_time = datetime.utcnow()
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            await db.execute(
                sa.update(APICall)
                .where(APICall.id == api_call_id)
                .values(
                    status_code=500,
                    error_message=str(e),
                    response_time_ms=response_time_ms
                )
            )
            await db.commit()
            yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
    
    return StreamingResponse(generate(), media_type="text/plain")

# Admin endpoints
@app.post("/admin/api-keys")
async def create_api_key(
    name: str,
    db: AsyncSession = Depends(get_db)
):
    # Generate new API key
    api_key = f"sk-{uuid.uuid4().hex}"
    key_hash = bcrypt.hashpw(api_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Save to database
    new_key = APIKey(
        key_hash=key_hash,
        name=name,
        expires_at=datetime.utcnow() + timedelta(days=365)  # 1 year expiry
    )
    db.add(new_key)
    await db.commit()
    
    return {"api_key": api_key, "name": name, "id": str(new_key.id)}

@app.get("/admin/servers")
async def list_servers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(sa.select(ModelServer).where(ModelServer.is_active == True))
    servers = result.scalars().all()
    
    return [
        {
            "id": str(server.id),
            "name": server.name,
            "endpoint": server.endpoint,
            "models": server.models,
            "weight": server.weight,
            "health_score": float(server.health_score),
            "last_health_check": server.last_health_check.isoformat() if server.last_health_check else None
        }
        for server in servers
    ]

@app.post("/admin/servers")
async def register_server(
    name: str,
    endpoint: str,
    models: list,
    weight: int = 1,
    db: AsyncSession = Depends(get_db)
):
    # Add new server to database
    new_server = ModelServer(
        name=name,
        endpoint=endpoint,
        models=models,
        weight=weight
    )
    db.add(new_server)
    await db.commit()
    
    # Update LiteLLM router configuration
    await update_litellm_config(db)
    
    return {"id": str(new_server.id), "name": name, "endpoint": endpoint}

async def update_litellm_config(db: AsyncSession):
    """Update LiteLLM router with current server configuration"""
    result = await db.execute(sa.select(ModelServer).where(ModelServer.is_active == True))
    servers = result.scalars().all()
    
    model_list = []
    for server in servers:
        for model in server.models:
            model_list.append({
                "model_name": model,
                "litellm_params": {
                    "model": f"openai/{model}",
                    "api_base": f"{server.endpoint}/v1",
                    "api_key": "dummy-key",  # Your servers might not need auth
                    "weight": server.weight
                }
            })
    
    # Update LiteLLM router
    global litellm_router
    litellm_router.model_list = model_list
    litellm_router.reset_cache()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
