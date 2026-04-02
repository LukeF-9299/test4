"""
OpenAI-compatible API endpoints for Lite LLM API Service
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, AsyncGenerator
from fastapi import HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import structlog

from litellm_config import litellm_manager
from auth import require_api_key, log_request, APIKey
from database import APICall, get_usage_logs_db, db_manager
from config import settings

logger = structlog.get_logger()


# Pydantic models for request/response
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stream: Optional[bool] = False
    stop: Optional[list[str]] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    user: Optional[str] = None


class CompletionRequest(BaseModel):
    model: str
    prompt: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stream: Optional[bool] = False
    stop: Optional[list[str]] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    user: Optional[str] = None


class ErrorResponse(BaseModel):
    error: Dict[str, Any]


class UsageLogger:
    """Handles logging of API usage and metrics"""
    
    @staticmethod
    async def log_api_call(
        api_key_id: str,
        model: str,
        request_data: Dict[str, Any],
        response_data: Optional[Dict[str, Any]] = None,
        error_data: Optional[Dict[str, Any]] = None,
        start_time: datetime = None,
        end_time: datetime = None,
        request_id: str = None
    ):
        """Log API call to usage database"""
        
        if not start_time:
            start_time = datetime.utcnow()
        if not end_time:
            end_time = datetime.utcnow()
        if not request_id:
            request_id = str(uuid.uuid4())
        
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        try:
            async with db_manager.get_usage_logs_session() as db:
                api_call = APICall(
                    api_key_id=api_key_id,
                    model=model,
                    server_endpoint="litellm-router",  # Updated by LiteLLM
                    request_tokens=response_data.get("usage", {}).get("prompt_tokens") if response_data else None,
                    response_tokens=response_data.get("usage", {}).get("completion_tokens") if response_data else None,
                    total_tokens=response_data.get("usage", {}).get("total_tokens") if response_data else None,
                    response_time_ms=response_time_ms,
                    status_code=200 if response_data else 500,
                    error_message=error_data.get("error") if error_data else None,
                    timestamp=start_time,
                    request_id=request_id
                )
                
                db.add(api_call)
                await db.commit()
                
                logger.info("API call logged", 
                           request_id=request_id, 
                           model=model, 
                           response_time_ms=response_time_ms,
                           status_code=api_call.status_code)
                
        except Exception as e:
            logger.error("Failed to log API call", 
                        request_id=request_id, 
                        error=str(e))


# API Endpoints

async def chat_completions_handler(
    request: ChatCompletionRequest,
    api_key: APIKey = Depends(require_api_key),
    http_request: Request = None
) -> Dict[str, Any]:
    """Handle chat completion requests"""
    
    request_id = str(uuid.uuid4())
    start_time = datetime.utcnow()
    
    # Log the request
    await log_request(http_request, api_key)
    
    logger.info("Chat completion request started", 
               request_id=request_id, 
               model=request.model, 
               stream=request.stream,
               api_key_id=str(api_key.id))
    
    try:
        # Convert request to LiteLLM format
        lite_request = {
            "model": request.model,
            "messages": [{"role": msg.role, "content": msg.content} for msg in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": request.stream,
            "stop": request.stop,
            "presence_penalty": request.presence_penalty,
            "frequency_penalty": request.frequency_penalty,
            "user": request.user or str(api_key.id)
        }
        
        # Remove None values
        lite_request = {k: v for k, v in lite_request.items() if v is not None}
        
        if request.stream:
            return await handle_streaming_chat_completion(
                lite_request, request_id, api_key.id, start_time
            )
        else:
            return await handle_regular_chat_completion(
                lite_request, request_id, api_key.id, start_time
            )
            
    except Exception as e:
        end_time = datetime.utcnow()
        error_data = {"error": str(e), "type": type(e).__name__}
        
        # Log the error
        await UsageLogger.log_api_call(
            api_key_id=str(api_key.id),
            model=request.model,
            request_data=lite_request,
            error_data=error_data,
            start_time=start_time,
            end_time=end_time,
            request_id=request_id
        )
        
        logger.error("Chat completion failed", 
                   request_id=request_id, 
                   error=str(e),
                   model=request.model)
        
        raise HTTPException(
            status_code=500,
            detail={"error": {"message": str(e), "type": "internal_error"}}
        )


async def handle_regular_chat_completion(
    lite_request: Dict[str, Any],
    request_id: str,
    api_key_id: str,
    start_time: datetime
) -> Dict[str, Any]:
    """Handle regular (non-streaming) chat completion"""
    
    try:
        response = await litellm_manager.completion(**lite_request)
        
        end_time = datetime.utcnow()
        
        # Log successful response
        await UsageLogger.log_api_call(
            api_key_id=api_key_id,
            model=lite_request["model"],
            request_data=lite_request,
            response_data=response.model_dump() if hasattr(response, 'model_dump') else dict(response),
            start_time=start_time,
            end_time=end_time,
            request_id=request_id
        )
        
        logger.info("Chat completion successful", 
                   request_id=request_id,
                   model=lite_request["model"],
                   tokens_used=getattr(response, 'usage', {}).get('total_tokens', 0))
        
        return response
        
    except Exception as e:
        end_time = datetime.utcnow()
        error_data = {"error": str(e), "type": type(e).__name__}
        
        # Log the error
        await UsageLogger.log_api_call(
            api_key_id=api_key_id,
            model=lite_request["model"],
            request_data=lite_request,
            error_data=error_data,
            start_time=start_time,
            end_time=end_time,
            request_id=request_id
        )
        
        raise


async def handle_streaming_chat_completion(
    lite_request: Dict[str, Any],
    request_id: str,
    api_key_id: str,
    start_time: datetime
) -> StreamingResponse:
    """Handle streaming chat completion"""
    
    async def generate_stream():
        try:
            response = await litellm_manager.completion(**lite_request)
            
            # For streaming, LiteLLM returns an async generator
            async for chunk in response:
                # Format as Server-Sent Events
                chunk_data = chunk.model_dump() if hasattr(chunk, 'model_dump') else dict(chunk)
                yield f"data: {json.dumps(chunk_data)}\n\n"
            
            # Send final chunk
            yield "data: [DONE]\n\n"
            
            # Log completion (without detailed token usage for streaming)
            end_time = datetime.utcnow()
            await UsageLogger.log_api_call(
                api_key_id=api_key_id,
                model=lite_request["model"],
                request_data=lite_request,
                start_time=start_time,
                end_time=end_time,
                request_id=request_id
            )
            
            logger.info("Streaming chat completion successful", 
                       request_id=request_id,
                       model=lite_request["model"])
            
        except Exception as e:
            end_time = datetime.utcnow()
            error_data = {"error": str(e), "type": type(e).__name__}
            
            # Log the error
            await UsageLogger.log_api_call(
                api_key_id=api_key_id,
                model=lite_request["model"],
                request_data=lite_request,
                error_data=error_data,
                start_time=start_time,
                end_time=end_time,
                request_id=request_id
            )
            
            # Send error to client
            error_chunk = {
                "error": {
                    "message": str(e),
                    "type": "streaming_error",
                    "code": "internal_error"
                }
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            
            logger.error("Streaming chat completion failed", 
                       request_id=request_id,
                       error=str(e),
                       model=lite_request["model"])
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


async def completions_handler(
    request: CompletionRequest,
    api_key: APIKey = Depends(require_api_key),
    http_request: Request = None
) -> Dict[str, Any]:
    """Handle text completion requests"""
    
    request_id = str(uuid.uuid4())
    start_time = datetime.utcnow()
    
    # Log the request
    await log_request(http_request, api_key)
    
    logger.info("Completion request started", 
               request_id=request_id, 
               model=request.model, 
               stream=request.stream,
               api_key_id=str(api_key.id))
    
    try:
        # Convert request to LiteLLM format
        lite_request = {
            "model": request.model,
            "prompt": request.prompt,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": request.stream,
            "stop": request.stop,
            "presence_penalty": request.presence_penalty,
            "frequency_penalty": request.frequency_penalty,
            "user": request.user or str(api_key.id)
        }
        
        # Remove None values
        lite_request = {k: v for k, v in lite_request.items() if v is not None}
        
        if request.stream:
            return await handle_streaming_completion(
                lite_request, request_id, api_key.id, start_time
            )
        else:
            return await handle_regular_completion(
                lite_request, request_id, api_key.id, start_time
            )
            
    except Exception as e:
        end_time = datetime.utcnow()
        error_data = {"error": str(e), "type": type(e).__name__}
        
        # Log the error
        await UsageLogger.log_api_call(
            api_key_id=str(api_key.id),
            model=request.model,
            request_data=lite_request,
            error_data=error_data,
            start_time=start_time,
            end_time=end_time,
            request_id=request_id
        )
        
        logger.error("Completion failed", 
                   request_id=request_id, 
                   error=str(e),
                   model=request.model)
        
        raise HTTPException(
            status_code=500,
            detail={"error": {"message": str(e), "type": "internal_error"}}
        )


async def handle_regular_completion(
    lite_request: Dict[str, Any],
    request_id: str,
    api_key_id: str,
    start_time: datetime
) -> Dict[str, Any]:
    """Handle regular (non-streaming) completion"""
    
    try:
        response = await litellm_manager.completion(**lite_request)
        
        end_time = datetime.utcnow()
        
        # Log successful response
        await UsageLogger.log_api_call(
            api_key_id=api_key_id,
            model=lite_request["model"],
            request_data=lite_request,
            response_data=response.model_dump() if hasattr(response, 'model_dump') else dict(response),
            start_time=start_time,
            end_time=end_time,
            request_id=request_id
        )
        
        logger.info("Completion successful", 
                   request_id=request_id,
                   model=lite_request["model"],
                   tokens_used=getattr(response, 'usage', {}).get('total_tokens', 0))
        
        return response
        
    except Exception as e:
        end_time = datetime.utcnow()
        error_data = {"error": str(e), "type": type(e).__name__}
        
        # Log the error
        await UsageLogger.log_api_call(
            api_key_id=api_key_id,
            model=lite_request["model"],
            request_data=lite_request,
            error_data=error_data,
            start_time=start_time,
            end_time=end_time,
            request_id=request_id
        )
        
        raise


async def handle_streaming_completion(
    lite_request: Dict[str, Any],
    request_id: str,
    api_key_id: str,
    start_time: datetime
) -> StreamingResponse:
    """Handle streaming completion"""
    
    async def generate_stream():
        try:
            response = await litellm_manager.completion(**lite_request)
            
            # For streaming, LiteLLM returns an async generator
            async for chunk in response:
                # Format as Server-Sent Events
                chunk_data = chunk.model_dump() if hasattr(chunk, 'model_dump') else dict(chunk)
                yield f"data: {json.dumps(chunk_data)}\n\n"
            
            # Send final chunk
            yield "data: [DONE]\n\n"
            
            # Log completion (without detailed token usage for streaming)
            end_time = datetime.utcnow()
            await UsageLogger.log_api_call(
                api_key_id=api_key_id,
                model=lite_request["model"],
                request_data=lite_request,
                start_time=start_time,
                end_time=end_time,
                request_id=request_id
            )
            
            logger.info("Streaming completion successful", 
                       request_id=request_id,
                       model=lite_request["model"])
            
        except Exception as e:
            end_time = datetime.utcnow()
            error_data = {"error": str(e), "type": type(e).__name__}
            
            # Log the error
            await UsageLogger.log_api_call(
                api_key_id=api_key_id,
                model=lite_request["model"],
                request_data=lite_request,
                error_data=error_data,
                start_time=start_time,
                end_time=end_time,
                request_id=request_id
            )
            
            # Send error to client
            error_chunk = {
                "error": {
                    "message": str(e),
                    "type": "streaming_error",
                    "code": "internal_error"
                }
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            
            logger.error("Streaming completion failed", 
                       request_id=request_id,
                       error=str(e),
                       model=lite_request["model"])
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


async def models_handler(api_key: APIKey = Depends(require_api_key)) -> Dict[str, Any]:
    """List available models"""
    
    try:
        models = await litellm_manager.get_available_models()
        
        logger.info("Models listed", count=len(models), api_key_id=str(api_key.id))
        
        return {
            "object": "list",
            "data": models
        }
        
    except Exception as e:
        logger.error("Failed to list models", error=str(e))
        raise HTTPException(
            status_code=500,
            detail={"error": {"message": "Failed to list models", "type": "internal_error"}}
        )
