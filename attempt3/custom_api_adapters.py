"""
Custom API adapters for non-OpenAI compatible endpoints
"""

import asyncio
import httpx
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import structlog

logger = structlog.get_logger()


class BaseAPIAdapter(ABC):
    """Base class for custom API adapters"""
    
    def __init__(self, server_config: Dict[str, Any]):
        self.server_config = server_config
        self.endpoint = server_config.get("endpoint", "")
        self.models = server_config.get("models", [])
        self.api_key = server_config.get("api_key", None)
        self.weight = server_config.get("weight", 1)
    
    @abstractmethod
    async def completion(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle completion request"""
        pass
    
    @abstractmethod
    async def embedding(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle embedding request"""
        pass
    
    @abstractmethod
    def transform_request(self, request: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Transform OpenAI-format request to provider-specific format"""
        pass
    
    @abstractmethod
    def transform_response(self, response: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Transform provider-specific response to OpenAI format"""
        pass


class HuggingFaceAdapter(BaseAPIAdapter):
    """Adapter for Hugging Face Inference API"""
    
    async def completion(self, request: Dict[str, Any]) -> Dict[str, Any]:
        model = request.get("model")
        hf_request = self.transform_request(request, model)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.endpoint}/models/{model}",
                json=hf_request,
                headers=self._get_headers()
            )
            response.raise_for_status()
            
            return self.transform_response(response.json(), model)
    
    async def embedding(self, request: Dict[str, Any]) -> Dict[str, Any]:
        model = request.get("model")
        inputs = request.get("input", "")
        
        hf_request = {
            "inputs": inputs,
            "options": {
                "use_cache": False,
                "wait_for_model": True
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.endpoint}/models/{model}",
                json=hf_request,
                headers=self._get_headers()
            )
            response.raise_for_status()
            
            # Transform Hugging Face embedding response to OpenAI format
            hf_response = response.json()
            
            return {
                "object": "list",
                "data": [{
                    "object": "embedding",
                    "embedding": hf_response[0].get("embedding", []),
                    "index": 0
                }],
                "model": model,
                "usage": {
                    "prompt_tokens": len(inputs.split()),
                    "total_tokens": len(inputs.split())
                }
            }
    
    def transform_request(self, request: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Transform OpenAI chat completion to Hugging Face format"""
        messages = request.get("messages", [])
        
        # Convert messages to a single prompt
        if messages:
            prompt = ""
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    prompt += f"System: {content}\n"
                elif role == "user":
                    prompt += f"Human: {content}\n"
                elif role == "assistant":
                    prompt += f"Assistant: {content}\n"
            
            prompt = prompt.strip()
        else:
            prompt = request.get("prompt", "")
        
        # Hugging Face parameters
        hf_params = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": request.get("max_tokens", 100),
                "temperature": request.get("temperature", 0.7),
                "top_p": request.get("top_p", 0.9),
                "stop": request.get("stop", []),
                "return_full_text": False
            }
        }
        
        return hf_params
    
    def transform_response(self, response: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Transform Hugging Face response to OpenAI format"""
        if isinstance(response, list) and len(response) > 0:
            generated_text = response[0].get("generated_text", "")
            
            # Extract only the newly generated part
            if "Human:" in generated_text:
                parts = generated_text.split("Human:")
                if len(parts) > 1:
                    new_text = parts[0].split("Assistant:")[-1].strip()
                else:
                    new_text = generated_text
            else:
                new_text = generated_text
            
            return {
                "id": f"hf-{hash(generated_text) % 1000000}",
                "object": "chat.completion",
                "created": asyncio.get_event_loop().time(),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": new_text
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": len(generated_text.split()) // 2,
                    "completion_tokens": len(new_text.split()),
                    "total_tokens": len(generated_text.split())
                }
            }
        
        return response
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


class CustomRESTAdapter(BaseAPIAdapter):
    """Adapter for custom REST APIs"""
    
    def __init__(self, server_config: Dict[str, Any]):
        super().__init__(server_config)
        self.completion_endpoint = server_config.get("endpoints", {}).get("completion", "/generate")
        self.embedding_endpoint = server_config.get("endpoints", {}).get("embedding", "/embed")
        self.request_format = server_config.get("request_format", "openai")
        self.response_format = server_config.get("response_format", "openai")
    
    async def completion(self, request: Dict[str, Any]) -> Dict[str, Any]:
        model = request.get("model")
        
        if self.request_format == "openai":
            custom_request = request
        else:
            custom_request = self.transform_request(request, model)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.endpoint}{self.completion_endpoint}",
                json=custom_request,
                headers=self._get_headers()
            )
            response.raise_for_status()
            
            if self.response_format == "openai":
                return response.json()
            else:
                return self.transform_response(response.json(), model)
    
    async def embedding(self, request: Dict[str, Any]) -> Dict[str, Any]:
        model = request.get("model")
        
        if self.request_format == "openai":
            custom_request = request
        else:
            custom_request = self.transform_request(request, model)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.endpoint}{self.embedding_endpoint}",
                json=custom_request,
                headers=self._get_headers()
            )
            response.raise_for_status()
            
            if self.response_format == "openai":
                return response.json()
            else:
                return self.transform_response(response.json(), model)
    
    def transform_request(self, request: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Override for custom request transformation"""
        # Default: pass through unchanged
        return request
    
    def transform_response(self, response: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Override for custom response transformation"""
        # Default: pass through unchanged
        return response
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


class CustomAPIManager:
    """Manager for custom API adapters"""
    
    def __init__(self):
        self.adapters: Dict[str, BaseAPIAdapter] = {}
        self._register_default_adapters()
    
    def _register_default_adapters(self):
        """Register built-in adapters"""
        self.adapters["huggingface"] = HuggingFaceAdapter
        self.adapters["custom"] = CustomRESTAdapter
    
    def register_adapter(self, name: str, adapter_class: type):
        """Register a custom adapter"""
        self.adapters[name] = adapter_class
    
    def create_adapter(self, server_config: Dict[str, Any]) -> BaseAPIAdapter:
        """Create adapter instance for server configuration"""
        adapter_type = server_config.get("adapter_type", "openai")
        
        if adapter_type == "openai":
            # Use standard LiteLLM for OpenAI-compatible
            return None
        elif adapter_type in self.adapters:
            adapter_class = self.adapters[adapter_type]
            return adapter_class(server_config)
        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")
    
    async def handle_request(self, server_config: Dict[str, Any], request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle request through appropriate adapter"""
        adapter = self.create_adapter(server_config)
        
        if adapter is None:
            # Fall back to standard LiteLLM handling
            return None
        
        # Determine request type
        if "input" in request or "embeddings" in str(request.get("model", "")):
            return await adapter.embedding(request)
        else:
            return await adapter.completion(request)


# Global custom API manager
custom_api_manager = CustomAPIManager()
