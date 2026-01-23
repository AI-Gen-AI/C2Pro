# Cache Service - Usage Guide

## Overview

The C2Pro cache service provides a robust Redis-based caching layer with automatic fallback to in-memory cache if Redis is unavailable. It's designed with "soft failure" in mind - the application never crashes due to cache issues.

## Features

- ✅ **Async Redis client** with connection pooling
- ✅ **SSL/TLS support** for Upstash and production environments
- ✅ **Automatic JSON serialization/deserialization**
- ✅ **Soft failure**: Falls back to in-memory cache if Redis is down
- ✅ **Namespace support** with key prefixes (e.g., `c2pro:project:{id}:...`)
- ✅ **TTL (Time To Live)** for automatic expiration
- ✅ **Metrics integration** for cache hit/miss tracking

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# For production (Upstash with SSL/TLS)
REDIS_URL=rediss://default:your-password@your-redis.upstash.io:6379

# For local development
REDIS_URL=redis://localhost:6379

# Optional: cache TTL settings
CACHE_TTL_DEFAULT=300
CACHE_TTL_AI_RESPONSE=3600
```

### Initialize in FastAPI

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.cache import init_cache, close_cache

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_cache(namespace_prefix="c2pro")
    yield
    # Shutdown
    await close_cache()

app = FastAPI(lifespan=lifespan)
```

## Basic Usage

### Get Cache Service

```python
from src.core.cache import get_cache_service

cache = get_cache_service()
```

### Set and Get Values

```python
# Set a value with TTL
await cache.set("user:123", {"name": "John", "email": "john@example.com"}, ttl=300)

# Get a value
user = await cache.get("user:123")
# Returns: {"name": "John", "email": "john@example.com"}

# Get with default value
user = await cache.get("user:999", default={"name": "Anonymous"})
# Returns: {"name": "Anonymous"} if key doesn't exist
```

### Delete and Check Existence

```python
# Check if key exists
exists = await cache.exists("user:123")
# Returns: True or False

# Delete a key
deleted = await cache.delete("user:123")
# Returns: True if deleted, False if key didn't exist
```

## Namespace Support

Namespaces help organize cache keys and allow for bulk operations (e.g., clearing all cache for a tenant).

```python
# Use custom namespace
await cache.set(
    "session:abc123",
    {"user_id": "123", "expires": "2024-01-01"},
    ttl=3600,
    namespace="tenant:5"
)
# Actual key: "tenant:5:session:abc123"

# Get from namespace
session = await cache.get("session:abc123", namespace="tenant:5")

# Use predefined namespaces
from src.core.cache import NAMESPACE_PROJECT, NAMESPACE_USER

await cache.set("summary", project_data, namespace=f"{NAMESPACE_PROJECT}:123")
# Actual key: "project:123:summary"
```

## Domain-Specific Methods

### Document Extraction Cache

```python
from src.core.cache import build_document_hash

# Cache extraction results
document_content = b"..."
doc_hash = build_document_hash(document_content)

await cache.set_extraction(
    document_hash=doc_hash,
    task_type="clauses",
    payload={"clauses": [...]},
    ttl_seconds=86400  # 24 hours
)

# Retrieve cached extraction
result = await cache.get_extraction(doc_hash, "clauses")
```

### Project Cache

```python
from src.core.cache import build_project_cache_key

# Cache project summary
key = build_project_cache_key("project-uuid", "summary")
await cache.set_json(key, project_summary, ttl_seconds=3600)

# Get cached summary
summary = await cache.get_json(key)
```

### Rate Limiting

```python
from src.core.cache import build_rate_limit_key

# Track API rate limits
key = build_rate_limit_key("user-uuid", "/api/v1/projects")

# Increment counter
if cache._redis:
    await cache._redis.incr(key)
    await cache._redis.expire(key, 60)  # 60 seconds window
```

## Advanced Usage

### Custom TTL Constants

```python
from src.core.cache import (
    EXTRACTION_TTL_SECONDS,  # 24 hours
    PROJECT_TTL_SECONDS,      # 1 hour
    ANALYSIS_TTL_SECONDS      # 30 minutes
)

await cache.set("analysis:123", result, ttl=ANALYSIS_TTL_SECONDS)
```

### Soft Failure Behavior

The cache service is designed to never crash your application:

```python
# If Redis is down, this will:
# 1. Log a warning
# 2. Fall back to in-memory cache
# 3. Return the result (or None)
# 4. Your application continues running

result = await cache.get("some:key")
# Always safe to call, even if Redis is down
```

### Check Cache Status

```python
# Check if Redis is available
is_available = await cache.ping()
# Returns: True if Redis is up, False otherwise

# Check if cache is enabled
if cache.enabled:
    print("Redis cache is active")
else:
    print("Using in-memory fallback")
```

## Best Practices

### 1. Always Use Namespaces

```python
# ✅ Good: organized, easy to manage
await cache.set("user:data", data, namespace="tenant:5")

# ❌ Bad: flat keys, hard to manage
await cache.set("tenant5_user_data", data)
```

### 2. Set Appropriate TTLs

```python
# ✅ Good: short TTL for frequently changing data
await cache.set("user:online_status", status, ttl=60)

# ✅ Good: long TTL for static data
await cache.set("config:site_settings", settings, ttl=86400)

# ❌ Bad: no TTL for temporary data
await cache.set("session:temp", data)  # Will never expire!
```

### 3. Handle Cache Misses Gracefully

```python
# ✅ Good: check for None
user = await cache.get("user:123")
if user is None:
    user = await db.query_user(123)
    await cache.set("user:123", user, ttl=300)

# ✅ Good: use default value
user = await cache.get("user:123", default={})
```

### 4. Cache Expensive Operations

```python
# ✅ Good: cache AI responses
async def analyze_document(doc_id: str):
    cache_key = f"analysis:{doc_id}"

    # Try cache first
    result = await cache.get(cache_key)
    if result:
        return result

    # Expensive AI call
    result = await ai_service.analyze(doc_id)

    # Cache for 1 hour
    await cache.set(cache_key, result, ttl=3600)
    return result
```

## Error Handling

The cache service handles errors gracefully:

```python
# All operations are safe and won't crash
await cache.set("key", "value")  # Logs error if Redis fails, continues
value = await cache.get("key")   # Returns None if Redis fails
await cache.delete("key")        # Returns False if Redis fails
exists = await cache.exists("key") # Returns False if Redis fails
```

## Testing

### Mock Cache in Tests

```python
from unittest.mock import AsyncMock

async def test_my_function():
    # Mock cache service
    mock_cache = AsyncMock()
    mock_cache.get.return_value = {"name": "John"}

    # Your test code here
    result = await my_function(mock_cache)

    # Verify cache was called
    mock_cache.get.assert_called_once_with("user:123")
```

## Troubleshooting

### Redis Connection Issues

If you see warnings like `cache_unavailable`:

1. Check `REDIS_URL` in `.env`
2. Verify Redis server is running: `redis-cli ping`
3. For Upstash, check SSL/TLS: URL should start with `rediss://`

### Memory Usage

The in-memory fallback cache is unbounded. If Redis is down for extended periods, monitor memory usage:

```python
# Clear in-memory cache manually if needed
if not cache.enabled:
    await cache._memory.close()
```

## Performance Tips

1. **Batch Operations**: Use namespaces to organize related keys
2. **TTL Strategy**: Shorter TTLs for frequently updated data
3. **Cache Warming**: Pre-populate cache on startup for critical data
4. **Monitor Metrics**: Check cache hit/miss ratios using observability tools
