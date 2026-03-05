# Simple Redis Cache

A minimalist, easy-to-understand Redis cache for FastAPI applications.

## Features

- ✅ **Simple API**: Easy to use and understand
- ✅ **Async Support**: Full async/await compatibility  
- ✅ **JSON Serialization**: Automatic JSON encoding/decoding
- ✅ **TTL Support**: Configurable expiration times
- ✅ **FastAPI Integration**: Dependency injection ready
- ✅ **Cache Decorator**: Automatic function result caching
- ✅ **Error Handling**: Graceful fallbacks when Redis is unavailable

## Quick Start

### Basic Usage

```python
from app.core.cache import cache

# Set a value (default TTL: 1 hour)
await cache.set("user:123", {"name": "John", "email": "john@example.com"})

# Get a value
user = await cache.get("user:123")

# Set with custom TTL (30 minutes)
await cache.set("session:abc", session_data, ttl=1800)

# Delete a key
await cache.delete("user:123")

# Check if key exists
exists = await cache.exists("user:123")
```

### FastAPI Dependency Injection

```python
from fastapi import Depends
from app.core.cache import get_cache, Cache

@app.get("/users/{user_id}")
async def get_user(user_id: int, cache: Cache = Depends(get_cache)):
    # Try cache first
    user = await cache.get(f"user:{user_id}")
    
    if not user:
        # Fetch from database
        user = await fetch_user_from_db(user_id)
        # Cache for 1 hour
        await cache.set(f"user:{user_id}", user, ttl=3600)
    
    return user
```

### Cache Decorator

```python
from app.core.cache import cached

@cached(ttl=1800)  # Cache for 30 minutes
async def get_user_stats(user_id: int):
    # This expensive operation will be cached
    return await calculate_user_statistics(user_id)

@cached(ttl=3600, key_prefix="products")
async def get_product(product_id: int):
    return await fetch_product_from_db(product_id)
```

### Cache Key Generation

```python
from app.core.cache import cache_key

# Generate structured keys
key = cache_key("user", user_id, namespace="profiles")  # "profiles:user:123"
key = cache_key(user_id, action="stats", namespace="users")  # "users:123:action:stats"
```

## Configuration

The cache uses your existing Redis settings from `settings.py`:

```python
REDIS_HOST: str = "localhost"
REDIS_PORT: int = 6379  
REDIS_DB: int = 0
REDIS_PASSWORD: str = ""  # Optional
```

## Error Handling

The cache gracefully handles Redis connection issues:

```python
async def get_user_safe(user_id: int):
    # Try cache first
    user = await cache.get(f"user:{user_id}")
    
    if user:
        return user
    
    # Fetch from database (cache will log errors but not fail)
    user = await fetch_user_from_db(user_id)
    
    # Try to cache (won't fail if Redis is down)
    await cache.set(f"user:{user_id}", user)
    
    return user
```

## Common Patterns

### User Caching

```python
from app.core.cache import cached

class UserService:
    @cached(ttl=3600, key_prefix="users")
    async def get_user(self, user_id: int):
        return await self.db.get_user(user_id)
    
    async def update_user(self, user_id: int, data: dict):
        # Update database
        user = await self.db.update_user(user_id, data)
        
        # Clear cache
        await cache.delete(f"users:get_user:{user_id}")
        
        return user
```

### API Response Caching

```python
@app.get("/products")
async def list_products(
    category: str = None,
    cache: Cache = Depends(get_cache)
):
    cache_key = f"products:list:{category or 'all'}"
    
    products = await cache.get(cache_key)
    if not products:
        products = await fetch_products(category)
        await cache.set(cache_key, products, ttl=600)  # 10 minutes
    
    return products
```

### Session Caching

```python
@app.post("/login")
async def login(credentials: LoginData, cache: Cache = Depends(get_cache)):
    user = await authenticate(credentials)
    
    session_id = generate_session_id()
    session_data = {"user_id": user.id, "expires": "..."}
    
    # Cache session for 30 minutes
    await cache.set(f"session:{session_id}", session_data, ttl=1800)
    
    return {"token": session_id}
```

## Health Monitoring

```python
@app.get("/health/cache")
async def cache_health():
    is_healthy = await cache.ping()
    return {"cache": "healthy" if is_healthy else "unhealthy"}
```

## Best Practices

1. **Use Descriptive Keys**: `user:123`, `session:abc`, `product:456`
2. **Set Appropriate TTLs**: 
   - User data: 1 hour (3600s)
   - API responses: 5-10 minutes (300-600s)
   - Sessions: 30 minutes (1800s)
3. **Handle Cache Misses**: Always have a fallback to fetch fresh data
4. **Clear Cache on Updates**: Remove cached data when underlying data changes
5. **Use Patterns for Bulk Operations**: `user:*` to clear all user data

## API Reference

### Cache Class

#### `set(key: str, value: Any, ttl: Optional[int] = None) -> bool`
Store a value in cache with optional TTL.

#### `get(key: str) -> Optional[Any]`
Retrieve a value from cache.

#### `delete(key: str) -> bool` 
Remove a key from cache.

#### `exists(key: str) -> bool`
Check if a key exists in cache.

#### `clear_pattern(pattern: str) -> int`
Delete all keys matching a pattern.

#### `ping() -> bool`
Check Redis connectivity.

### Functions

#### `get_cache() -> Cache`
FastAPI dependency for cache injection.

#### `cache_key(*args, namespace: str = "", **kwargs) -> str`
Generate cache keys from arguments.

#### `@cached(ttl: int = 3600, key_prefix: str = "")`
Decorator for automatic function result caching.

This simplified cache implementation gives you all the essential caching functionality you need while remaining easy to understand and maintain!