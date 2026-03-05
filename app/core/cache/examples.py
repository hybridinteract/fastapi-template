"""
Practical cache usage examples for your FastAPI application.

This file demonstrates how to integrate the cache system with your
user and service_provider modules effectively.
"""

import asyncio
from typing import List, Optional
from fastapi import Depends
from app.core.cache import cache, cached, get_cache, cache_invalidate_pattern, Cache
from app.core.logging import get_logger

logger = get_logger(__name__)


# ==================== Service Provider Examples ====================

class ServiceProviderService:
    """Example service provider service with caching."""

    @cached(ttl=3600, key_prefix="service_providers")
    async def get_service_provider(self, provider_id: int):
        """Cache service provider data for 1 hour."""
        # This would fetch from your database
        # return await self.db.get_service_provider(provider_id)
        pass

    @cached(ttl=1800, key_prefix="service_providers")
    async def get_provider_services(self, provider_id: int, category: str = None):
        """Cache provider services for 30 minutes."""
        # This would fetch services from database
        # return await self.db.get_provider_services(provider_id, category)
        pass

    @cache_invalidate_pattern("service_providers:*")
    async def update_service_provider(self, provider_id: int, data: dict):
        """Update provider and invalidate all related cache."""
        # Update in database
        # updated_provider = await self.db.update_service_provider(provider_id, data)

        # Cache invalidation happens automatically via decorator
        # return updated_provider
        pass

    async def get_provider_stats(self, provider_id: int):
        """Get provider stats with manual cache management."""
        cache_key = f"provider_stats:{provider_id}"

        # Try cache first
        stats = await cache.get(cache_key)
        if stats is not None:
            return stats

        # Calculate expensive stats
        # stats = await self.calculate_provider_statistics(provider_id)

        # Cache for 15 minutes
        # await cache.set(cache_key, stats, ttl=900)

        # return stats
        pass


# ==================== User Examples ====================

class UserService:
    """Example user service with caching patterns."""

    @cached(ttl=3600, key_prefix="users")
    async def get_user_profile(self, user_id: int):
        """Cache user profile for 1 hour."""
        # return await self.db.get_user(user_id)
        pass

    @cached(ttl=1800, key_prefix="users")
    async def get_user_permissions(self, user_id: int):
        """Cache user permissions for 30 minutes."""
        # return await self.permission_service.get_user_permissions(user_id)
        pass

    @cache_invalidate_pattern("users:get_user_permissions:*")
    async def update_user_role(self, user_id: int, role_id: int):
        """Update user role and invalidate permission caches."""
        # Update user role in database
        # result = await self.db.update_user_role(user_id, role_id)

        # Specific user cache invalidation
        # await cache.delete(f"users:get_user_profile:{user_id}")

        # return result
        pass

    async def search_users(self, query: str, page: int = 1, limit: int = 20):
        """Search users with query-specific caching."""
        # Create cache key from search parameters
        search_key = f"user_search:{hash(query)}:page:{page}:limit:{limit}"

        # Try cache first (5 minutes for search results)
        results = await cache.get(search_key)
        if results is not None:
            return results

        # Perform search
        # results = await self.db.search_users(query, page, limit)

        # Cache results
        # await cache.set(search_key, results, ttl=300)

        # return results
        pass


# ==================== FastAPI Route Examples ====================

# Example routes showing cache integration with dependency injection

async def get_cached_service_provider(
    provider_id: int,
    cache_client: Cache = Depends(get_cache)
):
    """FastAPI route with cache dependency injection."""
    # Try cache first
    provider = await cache_client.get(f"provider:{provider_id}")

    if not provider:
        # Fetch from database
        # provider = await fetch_provider_from_db(provider_id)

        # Cache for 1 hour
        # await cache_client.set(f"provider:{provider_id}", provider, ttl=3600)
        pass

    return provider


async def get_user_dashboard(
    user_id: int,
    cache_client: Cache = Depends(get_cache)
):
    """Complex dashboard data with multiple cache operations."""

    # Use bulk cache operations for efficiency
    cache_keys = [
        f"user_profile:{user_id}",
        f"user_stats:{user_id}",
        f"user_notifications:{user_id}"
    ]

    # Get multiple cached values at once
    cached_data = await cache_client.mget(cache_keys)
    profile, stats, notifications = cached_data

    dashboard_data = {}

    # Fetch missing data
    if not profile:
        # profile = await fetch_user_profile(user_id)
        # dashboard_data['profile'] = profile
        pass
    else:
        dashboard_data['profile'] = profile

    if not stats:
        # stats = await calculate_user_stats(user_id)
        # dashboard_data['stats'] = stats
        pass
    else:
        dashboard_data['stats'] = stats

    if not notifications:
        # notifications = await get_user_notifications(user_id)
        # dashboard_data['notifications'] = notifications
        pass
    else:
        dashboard_data['notifications'] = notifications

    # Cache any newly fetched data
    cache_updates = {}
    if not profile and 'profile' in dashboard_data:
        cache_updates[f"user_profile:{user_id}"] = dashboard_data['profile']
    if not stats and 'stats' in dashboard_data:
        cache_updates[f"user_stats:{user_id}"] = dashboard_data['stats']
    if not notifications and 'notifications' in dashboard_data:
        cache_updates[f"user_notifications:{user_id}"] = dashboard_data['notifications']

    # Bulk set cache data
    if cache_updates:
        await cache_client.mset(cache_updates, ttl=1800)  # 30 minutes

    return dashboard_data


# ==================== Advanced Patterns ====================

class AdvancedCachePatterns:
    """Advanced caching patterns for complex scenarios."""

    @staticmethod
    async def cache_with_tags(key: str, value: any, ttl: int, tags: List[str]):
        """Cache with tags for group invalidation."""
        # Store the main data
        await cache.set(key, value, ttl=ttl)

        # Store tag mappings
        for tag in tags:
            tag_key = f"tag:{tag}"
            tagged_keys = await cache.get(tag_key) or []
            if key not in tagged_keys:
                tagged_keys.append(key)
                await cache.set(tag_key, tagged_keys, ttl=ttl)

    @staticmethod
    async def invalidate_by_tag(tag: str):
        """Invalidate all cache entries with a specific tag."""
        tag_key = f"tag:{tag}"
        tagged_keys = await cache.get(tag_key) or []

        if tagged_keys:
            # Delete all tagged keys
            for key in tagged_keys:
                await cache.delete(key)

            # Delete the tag key itself
            await cache.delete(tag_key)

            return len(tagged_keys)
        return 0

    @staticmethod
    async def get_or_set_with_lock(key: str, fetch_func, ttl: int = 3600):
        """Prevent cache stampede with distributed locking."""
        lock_key = f"lock:{key}"

        # Try to get from cache first
        value = await cache.get(key)
        if value is not None:
            return value

        # Try to acquire lock
        # 30 second lock
        lock_acquired = await cache.set(f"lock:{key}", "locked", ttl=30)
        if not lock_acquired:
            # Another process is fetching, wait a bit and try cache again
            await asyncio.sleep(0.1)
            value = await cache.get(key)
            if value is not None:
                return value
            # If still no value, fetch anyway (lock might have expired)

        try:
            # Fetch the data
            value = await fetch_func()

            # Cache the result
            await cache.set(key, value, ttl=ttl)

            return value
        finally:
            # Release the lock
            await cache.delete(lock_key)


# ==================== Cache Health and Monitoring ====================

async def get_cache_health():
    """Get comprehensive cache health information."""
    try:
        stats = await cache.get_stats()
        return {
            "status": "healthy" if stats.get("connected", False) else "unhealthy",
            "stats": stats
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def warm_up_cache():
    """Warm up cache with frequently accessed data."""
    # This would be called during application startup
    try:
        # Pre-load frequently accessed data
        # common_users = await get_common_user_data()
        # for user in common_users:
        #     await cache.set(f"user:{user.id}", user.dict(), ttl=3600)

        # Pre-load configuration data
        # settings_data = await get_app_settings()
        # await cache.set("app_settings", settings_data, ttl=7200)

        pass
    except Exception as e:
        logger.error(f"Cache warm-up failed: {e}")


# ==================== Usage in Your Modules ====================

"""
To use this cache system in your existing modules:

1. In app/user/services.py:
   
   from app.core.cache import cached, cache_invalidate_pattern
   
   class UserService:
       @cached(ttl=3600, key_prefix="users")
       async def get_user(self, user_id: int):
           return await self.repository.get_user(user_id)
       
       @cache_invalidate_pattern("users:*")
       async def update_user(self, user_id: int, data: dict):
           return await self.repository.update_user(user_id, data)

2. In app/service_provider/routes.py:
   
   from app.core.cache import get_cache
   
   @router.get("/providers/{provider_id}")
   async def get_provider(
       provider_id: int,
       cache: Cache = Depends(get_cache)
   ):
       provider = await cache.get(f"provider:{provider_id}")
       if not provider:
           provider = await service.get_provider(provider_id)
           await cache.set(f"provider:{provider_id}", provider, ttl=1800)
       return provider

3. For bulk operations in app/user/crud.py:
   
   from app.core.cache import cache
   
   async def get_multiple_users(user_ids: List[int]):
       cache_keys = [f"user:{uid}" for uid in user_ids]
       cached_users = await cache.mget(cache_keys)
       
       # Handle cache misses and fetch from DB
       # ... implementation details
"""
