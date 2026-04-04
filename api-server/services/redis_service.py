"""
services/redis_service.py
Redis client singleton for the API server.
"""

import os
import redis

_client = None


def get_redis() -> redis.Redis:
    """Return a shared Redis client (lazy init)."""
    global _client
    if _client is None:
        pool = redis.ConnectionPool(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            max_connections=20,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=1,
        )
        _client = redis.Redis(connection_pool=pool)
    return _client
