#!/usr/bin/env python3
"""
Simple LLM and Embedding model functions using OpenAI library.
Compatible with vLLM OpenAI-compatible models.
"""

from openai import OpenAI
from typing import List


def llm_call(api_key: str, base_url: str, thinking_level: int, temperature: float, 
             system_prompt: str, user_prompt: str) -> str:
    """
    Make an LLM call using OpenAI-compatible API.
    
    Args:
        api_key: API key for authentication
        base_url: Base URL for the vLLM server
        thinking_level: Level of reasoning/thinking (1-10)
        temperature: Sampling temperature (0.0-2.0)
        system_prompt: System prompt/instructions
        user_prompt: User prompt/question
        
    Returns:
        Generated text response
    """
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )
    
    # Adjust system prompt based on thinking level
    if thinking_level > 5:
        system_prompt += "\n\nThink step-by-step and show your reasoning process."
    elif thinking_level > 8:
        system_prompt += "\n\nProvide detailed analysis with multiple perspectives."
    
    try:
        response = client.chat.completions.create(
            model="default",  # vLLM typically uses "default" or model name
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=2048,
            stream=False
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"Error: {str(e)}"


def embedding_call(api_key: str, base_url: str, texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings using OpenAI-compatible API.
    
    Args:
        api_key: API key for authentication
        base_url: Base URL for the vLLM server
        texts: List of strings to embed
        
    Returns:
        List of embedding vectors
    """
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )
    
    try:
        response = client.embeddings.create(
            model="default",  # vLLM typically uses "default" or embedding model name
            input=texts
        )
        
        # Extract embeddings from response
        embeddings = [data.embedding for data in response.data]
        return embeddings
        
    except Exception as e:
        print(f"Error generating embeddings: {str(e)}")
        return []


if __name__ == "__main__":
    # Example usage
    print("Testing LLM function:")
    
    llm_response = llm_call(
        api_key="test-key",
        base_url="http://localhost:8000/v1",
        thinking_level=7,
        temperature=0.7,
        system_prompt="You are a helpful assistant.",
        user_prompt="What is machine learning?"
    )
    
    print(f"LLM Response: {llm_response}")
    
    print("\nTesting Embedding function:")
    
    embeddings = embedding_call(
        api_key="test-key",
        base_url="http://localhost:8000/v1",
        texts=["Hello world", "Machine learning is fun", "Test sentence"]
    )
    
    print(f"Generated {len(embeddings)} embeddings")
    if embeddings:
        print(f"Embedding dimension: {len(embeddings[0])}")
        print(f"First embedding sample: {embeddings[0][:5]}...")
