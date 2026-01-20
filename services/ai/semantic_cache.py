# services/ai/semantic_cache.py
import asyncio
import json
import os
import time
from typing import List, Optional, Dict, Any

import numpy as np
import redis.asyncio as redis
from redis.commands.search.field import (
    VectorField,
    TagField,
    TextField,
    NumericField,
)
from redis.commands.search.query import Query
from sentence_transformers import SentenceTransformer

# --- Configuration ---
# Model for local embedding generation. Fast and effective for sentence similarity.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384  # Dimension for the 'all-MiniLM-L6-v2' model

# Redis connection settings (should be loaded from environment variables)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

# Semantic Cache settings
REDIS_INDEX_NAME = "semantic_cache_idx"
SIMILARITY_THRESHOLD = 0.95  # Minimum similarity to consider a cache hit
# Redis returns distance (1 - similarity), so the threshold for distance is 1 - 0.95
DISTANCE_THRESHOLD = 1 - SIMILARITY_THRESHOLD

# --- Embedding Service ---

class EmbeddingService:
    """
    A wrapper for the SentenceTransformer model to handle embedding generation.
    The model is loaded once and reused.
    """
    def __init__(self):
        print("Loading sentence-transformer model...")
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        print("Model loaded.")

    async def get_embedding(self, text: str) -> List[float]:
        """
        Generates an embedding for the given text.
        Runs the synchronous encoding process in a thread pool to avoid blocking asyncio event loop.
        """
        def _encode():
            return self.model.encode(text, convert_to_numpy=True)
        
        # Use asyncio.to_thread to run the CPU-bound operation in a separate thread
        embedding = await asyncio.to_thread(_encode)
        return embedding.tolist()

# --- Semantic Cache Service ---

class SemanticCache:
    """
    Manages storing and retrieving LLM responses from a Redis vector database.
    Ensures tenant isolation and uses a similarity threshold for cache hits.
    """
    def __init__(self, redis_client: redis.Redis, embedding_service: EmbeddingService):
        self.redis = redis_client
        self.embedding_service = embedding_service

    async def _create_index_if_not_exists(self):
        """
        Creates the Redis search index for vector similarity search if it doesn't already exist.
        """
        schema = (
            TagField("tenant_id"),
            TextField("original_prompt"),
            TextField("model_used"),
            NumericField("timestamp"),
            VectorField(
                "prompt_embedding",
                "HNSW",  # Using HNSW, a modern and high-performance index algorithm
                {
                    "TYPE": "FLOAT32",
                    "DIM": EMBEDDING_DIMENSION,
                    "DISTANCE_METRIC": "COSINE",
                },
            ),
            # Note: The response itself will be in the main JSON body, not indexed for search.
        )
        try:
            # Check if index exists
            await self.redis.ft(REDIS_INDEX_NAME).info()
            print(f"Index '{REDIS_INDEX_NAME}' already exists.")
        except redis.exceptions.ResponseError:
            # Index does not exist, so create it
            print(f"Creating index '{REDIS_INDEX_NAME}'...")
            await self.redis.ft(REDIS_INDEX_NAME).create_index(
                fields=schema,
                definition=redis.commands.search.indexDefinition.IndexDefinition(prefix=["cache:"])
            )
            print("Index created.")

    async def search(self, tenant_id: str, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Searches the cache for a semantically similar prompt for a specific tenant.
        """
        prompt_embedding = await self.embedding_service.get_embedding(prompt)
        
        # KNN query to find the nearest neighbor, filtered by tenant_id
        # We ask for K=1, sort by vector distance, and apply a filter for the tag.
        # The query is parametrized to prevent injection.
        query = (
            Query(f"(@tenant_id:{{{tenant_id}}})=>[KNN 1 @prompt_embedding $embedding AS score]")
            .sort_by("score")
            .return_fields("score", "response_json")
            .dialect(2)
        )
        
        query_params = {"embedding": np.array(prompt_embedding, dtype=np.float32).tobytes()}
        
        try:
            results = await self.redis.ft(REDIS_INDEX_NAME).search(query, query_params)
            
            if results.docs:
                best_match = results.docs[0]
                # 'score' is cosine distance. Lower is better.
                if float(best_match.score) <= DISTANCE_THRESHOLD:
                    print(f"CACHE HIT! Found similar prompt with score {1 - float(best_match.score):.4f}")
                    return json.loads(best_match.response_json)
        except Exception as e:
            print(f"Error during cache search: {e}")
            # If cache search fails, we proceed as a cache miss.
        
        print("CACHE MISS.")
        return None

    async def put(self, tenant_id: str, prompt: str, response: Dict[str, Any], model_used: str):
        """
        Stores a new prompt-response pair in the cache.
        """
        prompt_embedding = await self.embedding_service.get_embedding(prompt)
        
        cache_key = f"cache:{os.urandom(16).hex()}"
        
        pipeline = self.redis.pipeline()
        
        # Store the main data as a Redis Hash
        pipeline.hset(cache_key, mapping={
            "tenant_id": tenant_id,
            "original_prompt": prompt,
            "prompt_embedding": np.array(prompt_embedding, dtype=np.float32).tobytes(),
            "model_used": model_used,
            "timestamp": int(time.time()),
        })
        
        # Store the potentially large response JSON separately or as part of the hash if not too large
        pipeline.json().set(cache_key, "$.response_json", json.dumps(response))
        
        try:
            await pipeline.execute()
            print(f"Stored new entry in cache: {cache_key}")
        except Exception as e:
            print(f"Error during cache put: {e}")


# --- Integration Snippet ---

"""
Below is a hypothetical example of how to integrate the SemanticCache
into an existing service wrapper for an LLM like Anthropic.

class AnthropicWrapper:
    def __init__(self):
        # ... other initializations ...
        self.embedding_service = EmbeddingService()
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=False)
        self.semantic_cache = SemanticCache(redis_client, self.embedding_service)
        # It's important to create the index when the service starts up.
        # In a real app, this might be part of an async startup hook.
        asyncio.create_task(self.semantic_cache._create_index_if_not_exists())

    async def generate_completion(self, tenant_id: str, prompt: str, model: str, **kwargs) -> Dict[str, Any]:
        # 1. Check the semantic cache first
        cached_response = await self.semantic_cache.search(tenant_id=tenant_id, prompt=prompt)
        
        if cached_response:
            # Add a header or metadata to indicate this was a cache hit
            cached_response["_cache_info"] = {"hit": True, "type": "semantic"}
            return cached_response

        # 2. If it's a CACHE MISS, call the actual LLM
        # response = await call_anthropic_api(prompt, model, **kwargs) # Your actual API call
        response = {"generated_text": "This is a new response from the LLM."} # Placeholder

        # 3. Store the new response in the cache for future use
        # This can be done in the background to not delay returning the response to the user
        asyncio.create_task(self.semantic_cache.put(
            tenant_id=tenant_id,
            prompt=prompt,
            response=response,
            model_used=model
        ))
        
        response["_cache_info"] = {"hit": False}
        return response

"""
