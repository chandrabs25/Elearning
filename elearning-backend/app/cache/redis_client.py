"""Redis cache client using Upstash (free tier compatible)."""
import os
import json
from typing import Any

# Try to import upstash-redis (REST-based, serverless-friendly)
try:
    from upstash_redis import Redis
    UPSTASH_AVAILABLE = True
except ImportError:
    UPSTASH_AVAILABLE = False
    Redis = None


# Singleton client
_redis_client = None


def get_redis():
    """Get Upstash Redis client (lazy initialization)."""
    global _redis_client
    
    if not UPSTASH_AVAILABLE:
        return None
    
    if _redis_client is None:
        url = os.getenv("UPSTASH_REDIS_REST_URL")
        token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
        
        if url and token:
            _redis_client = Redis(url=url, token=token)
        else:
            print("Warning: UPSTASH_REDIS_REST_URL or UPSTASH_REDIS_REST_TOKEN not set")
            return None
    
    return _redis_client


async def cache_get(key: str) -> Any | None:
    """Get value from cache."""
    redis = get_redis()
    if not redis:
        return None
    
    try:
        value = redis.get(key)
        if value:
            return json.loads(value) if isinstance(value, str) else value
        return None
    except Exception as e:
        print(f"Redis get error: {e}")
        return None


from datetime import datetime

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


async def cache_set(key: str, value: Any, ttl: int = None):
    """Set value in cache. If ttl is None, cache permanently (LRU eviction only)."""
    redis = get_redis()
    if not redis:
        return
    
    try:
        # Convert to JSON string if not already
        if not isinstance(value, str):
            value_str = json.dumps(value, cls=DateTimeEncoder)
        else:
            value_str = value
            
        if ttl:
            redis.setex(key, ttl, value_str)
        else:
            redis.set(key, value_str)  # No expiration
    except Exception as e:
        print(f"Redis set error: {e}")


async def cache_delete(key: str):
    """Delete value from cache."""
    redis = get_redis()
    if not redis:
        return
    
    try:
        redis.delete(key)
    except Exception as e:
        print(f"Redis delete error: {e}")
