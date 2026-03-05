"""
Simple Redis Cache for FastAPI Application.

A minimalist, easy-to-understand Redis caching solution with:
- Simple async Redis operations
- JSON serialization
- Basic TTL support
- FastAPI dependency injection
- Cache decorator

Usage:
    from app.core.cache import cache, cached
    
    # Direct usage
    await cache.set("user:123", user_data, ttl=3600)
    user = await cache.get("user:123")
    
    # Dependency injection
    from app.core.cache import get_cache
    
    @app.get("/users/{user_id}")
    async def get_user(user_id: int, cache = Depends(get_cache)):
        return await cache.get(f"user:{user_id}")
    
    # Decorator usage
    @cached(ttl=3600)
    async def expensive_function(param: str):
        return await do_expensive_work(param)
"""

from .cache import (
    Cache,
    cache,
    get_cache,
    cached,
    cache_key,
    cache_invalidate_pattern
)

__all__ = [
    "Cache",
    "cache",
    "get_cache",
    "cached",
    "cache_key",
    "cache_invalidate_pattern"
]
