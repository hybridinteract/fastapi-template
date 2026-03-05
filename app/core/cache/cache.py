"""
Simple Redis Cache Implementation.

A minimalist, easy-to-understand Redis cache with modern FastAPI patterns.
"""

import json
import asyncio
from typing import Any, Optional, Union, Callable, List
from functools import wraps
import hashlib
from redis import asyncio as redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError

from app.core.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Cache:
    """
    Simple Redis cache with basic operations.

    Provides essential caching functionality with a clean, easy-to-use interface.
    """

    def __init__(self):
        """Initialize cache instance."""
        self._redis: Optional[redis.Redis] = None
        self._connected = False

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                retry_on_timeout=True,
                health_check_interval=30  # Health check every 30 seconds
            )
        return self._redis

    async def connect(self) -> bool:
        """
        Connect to Redis.

        Returns:
            bool: True if connected successfully
        """
        try:
            redis_client = await self._get_redis()
            await redis_client.ping()
            self._connected = True
            logger.info("✓ Redis cache connected")
            return True
        except Exception as e:
            logger.warning(f"⚠ Redis cache connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._connected = False
            logger.info("✓ Redis cache disconnected")

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set a value in cache.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (default: 1 hour)

        Returns:
            bool: True if successful
        """
        try:
            if not self._connected:
                await self.connect()

            redis_client = await self._get_redis()

            # Serialize value to JSON
            json_value = json.dumps(value, default=str, ensure_ascii=False)

            # Set with TTL (default 1 hour)
            if ttl is None:
                ttl = 3600

            await redis_client.setex(key, ttl, json_value)
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
            return True

        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Cache SET connection failed for key '{key}': {e}")
            return False
        except Exception as e:
            logger.error(f"Cache SET failed for key '{key}': {e}")
            return False

    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Optional[Any]: Cached value or None if not found
        """
        try:
            if not self._connected:
                await self.connect()

            redis_client = await self._get_redis()
            value = await redis_client.get(key)

            if value is None:
                logger.debug(f"Cache MISS: {key}")
                return None

            # Deserialize from JSON
            result = json.loads(value)
            logger.debug(f"Cache HIT: {key}")
            return result

        except json.JSONDecodeError:
            logger.error(f"Cache GET failed: Invalid JSON for key '{key}'")
            # Delete corrupted key
            await self.delete(key)
            return None
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Cache GET connection failed for key '{key}': {e}")
            return None
        except Exception as e:
            logger.error(f"Cache GET failed for key '{key}': {e}")
            return None

    async def delete(self, key: str) -> bool:
        """
        Delete a key from cache.

        Args:
            key: Cache key

        Returns:
            bool: True if key was deleted
        """
        try:
            if not self._connected:
                await self.connect()

            redis_client = await self._get_redis()
            result = await redis_client.delete(key)
            return result > 0

        except Exception as e:
            logger.error(f"Cache DELETE failed for key '{key}': {e}")
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.

        Args:
            key: Cache key

        Returns:
            bool: True if key exists
        """
        try:
            if not self._connected:
                await self.connect()

            redis_client = await self._get_redis()
            result = await redis_client.exists(key)
            return result > 0

        except Exception as e:
            logger.error(f"Cache EXISTS failed for key '{key}': {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "user:*")

        Returns:
            int: Number of keys deleted
        """
        try:
            if not self._connected:
                await self.connect()

            redis_client = await self._get_redis()
            keys = await redis_client.keys(pattern)

            if keys:
                deleted = await redis_client.delete(*keys)
                return deleted
            return 0

        except Exception as e:
            logger.error(
                f"Cache CLEAR_PATTERN failed for pattern '{pattern}': {e}")
            return 0

    async def ping(self) -> bool:
        """
        Check if Redis is accessible.

        Returns:
            bool: True if Redis responds to ping
        """
        try:
            redis_client = await self._get_redis()
            await redis_client.ping()
            return True
        except Exception:
            return False

    async def mget(self, keys: List[str]) -> List[Optional[Any]]:
        """
        Get multiple values from cache.

        Args:
            keys: List of cache keys

        Returns:
            List[Optional[Any]]: List of cached values (None for missing keys)
        """
        try:
            if not self._connected:
                await self.connect()

            redis_client = await self._get_redis()
            values = await redis_client.mget(keys)

            results = []
            for i, value in enumerate(values):
                if value is None:
                    results.append(None)
                    continue

                try:
                    results.append(json.loads(value))
                except json.JSONDecodeError:
                    logger.error(
                        f"Cache MGET failed: Invalid JSON for key '{keys[i]}'")
                    results.append(None)

            return results

        except Exception as e:
            logger.error(f"Cache MGET failed for keys {keys}: {e}")
            return [None] * len(keys)

    async def mset(self, mapping: dict, ttl: Optional[int] = None) -> bool:
        """
        Set multiple values in cache.

        Args:
            mapping: Dictionary of key-value pairs
            ttl: Time to live in seconds (default: 1 hour)

        Returns:
            bool: True if successful
        """
        try:
            if not self._connected:
                await self.connect()

            redis_client = await self._get_redis()

            # Serialize all values
            serialized_mapping = {}
            for key, value in mapping.items():
                try:
                    serialized_mapping[key] = json.dumps(
                        value, default=str, ensure_ascii=False)
                except Exception as e:
                    logger.error(
                        f"Cache MSET serialization failed for key '{key}': {e}")
                    continue

            if not serialized_mapping:
                return False

            # Set all values
            await redis_client.mset(serialized_mapping)

            # Set TTL for all keys if specified
            if ttl is not None:
                pipe = redis_client.pipeline()
                for key in serialized_mapping.keys():
                    pipe.expire(key, ttl)
                await pipe.execute()

            logger.debug(
                f"Cache MSET: {len(serialized_mapping)} keys (TTL: {ttl}s)")
            return True

        except Exception as e:
            logger.error(f"Cache MSET failed: {e}")
            return False

    async def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            dict: Cache statistics and info
        """
        try:
            if not self._connected:
                await self.connect()

            redis_client = await self._get_redis()
            info = await redis_client.info()

            return {
                "connected": True,
                "version": info.get("redis_version", "unknown"),
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_ratio": round(
                    info.get("keyspace_hits", 0) /
                    max(info.get("keyspace_hits", 0) +
                        info.get("keyspace_misses", 0), 1) * 100, 2
                )
            }

        except Exception as e:
            logger.error(f"Cache stats failed: {e}")
            return {"connected": False, "error": str(e)}


# Global cache instance
cache = Cache()


# FastAPI dependency
async def get_cache() -> Cache:
    """
    FastAPI dependency for cache injection.

    Usage:
        @app.get("/users/{user_id}")
        async def get_user(user_id: int, cache: Cache = Depends(get_cache)):
            return await cache.get(f"user:{user_id}")
    """
    if not cache._connected:
        await cache.connect()
    return cache


def cache_key(*args, namespace: str = "", separator: str = ":", **kwargs) -> str:
    """
    Generate a cache key from arguments.

    Args:
        *args: Positional arguments
        namespace: Optional namespace prefix
        separator: Key separator (default: ":")
        **kwargs: Keyword arguments

    Returns:
        str: Generated cache key
    """
    parts = []

    if namespace:
        parts.append(namespace)

    # Add positional arguments
    for arg in args:
        if hasattr(arg, 'id'):  # Database models with ID
            parts.append(
                f"{arg.__class__.__name__.lower()}{separator}{arg.id}")
        elif hasattr(arg, '__dict__'):  # Skip class instances for methods
            continue
        else:
            parts.append(str(arg))

    # Add keyword arguments (sorted for consistency)
    for key, value in sorted(kwargs.items()):
        parts.append(f"{key}{separator}{value}")

    key = separator.join(parts)

    # For very long keys, use hash to prevent Redis key length issues
    if len(key) > 250:  # Redis key length limit is 512MB, but 250 chars is practical
        key_hash = hashlib.md5(key.encode()).hexdigest()
        namespace_part = parts[0] if namespace else "hashed"
        key = f"{namespace_part}{separator}{key_hash}"

    return key


def cached(ttl: int = 3600, key_prefix: str = "", key_func: Optional[Callable] = None):
    """
    Decorator to cache function results.

    Args:
        ttl: Time to live in seconds (default: 1 hour)
        key_prefix: Optional key prefix
        key_func: Custom function to generate cache key

    Usage:
        @cached(ttl=1800, key_prefix="products")
        async def get_product(product_id: int):
            return await fetch_product_from_db(product_id)

        # Custom key generation
        @cached(ttl=3600, key_func=lambda user_id, **kw: f"user_profile:{user_id}")
        async def get_user_profile(user_id: int, include_settings: bool = False):
            return await fetch_user_profile(user_id, include_settings)
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                func_name = f"{func.__module__}.{func.__qualname__}"

                # Skip 'self' for class methods
                cache_args = args
                if args and hasattr(args[0], '__dict__'):
                    cache_args = args[1:]

                key_parts = [key_prefix,
                             func_name] if key_prefix else [func_name]
                key = cache_key(
                    *cache_args, namespace=":".join(filter(None, key_parts)), **kwargs)

            try:
                # Try to get from cache
                cached_result = await cache.get(key)
                if cached_result is not None:
                    logger.debug(f"Cache decorator HIT: {key}")
                    return cached_result

                # Cache miss - execute function
                logger.debug(f"Cache decorator MISS: {key}")
                result = await func(*args, **kwargs)

                # Cache the result
                await cache.set(key, result, ttl=ttl)

                return result

            except Exception as e:
                logger.error(
                    f"Cache decorator operation failed for {key}: {e}")
                # Fall back to executing function without cache
                return await func(*args, **kwargs)

        # Add cache invalidation method to the wrapper
        async def invalidate(*args, **kwargs):
            """Invalidate cached result for given arguments."""
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                func_name = f"{func.__module__}.{func.__qualname__}"
                cache_args = args
                if args and hasattr(args[0], '__dict__'):
                    cache_args = args[1:]
                key_parts = [key_prefix,
                             func_name] if key_prefix else [func_name]
                key = cache_key(
                    *cache_args, namespace=":".join(filter(None, key_parts)), **kwargs)

            return await cache.delete(key)

        wrapper.invalidate = invalidate
        wrapper._cache_key_func = key_func
        wrapper._cache_ttl = ttl
        wrapper._cache_prefix = key_prefix

        return wrapper
    return decorator


def cache_invalidate_pattern(pattern: str):
    """
    Decorator to invalidate cache patterns after function execution.

    Args:
        pattern: Redis key pattern to invalidate (e.g., "user:*", "products:category:*")

    Usage:
        @cache_invalidate_pattern("user:*")
        async def update_user(user_id: int, data: dict):
            # Update user in database
            return updated_user
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Execute the original function
                result = await func(*args, **kwargs)

                # Invalidate cache pattern after successful execution
                deleted_count = await cache.clear_pattern(pattern)
                if deleted_count > 0:
                    logger.info(
                        f"Cache invalidated {deleted_count} keys matching pattern: {pattern}")

                return result
            except Exception as e:
                # Don't invalidate cache if function failed
                logger.error(
                    f"Function {func.__name__} failed, cache not invalidated: {e}")
                raise

        return wrapper
    return decorator
