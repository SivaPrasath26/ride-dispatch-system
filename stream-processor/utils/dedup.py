"""
utils/dedup.py
Deduplication cache backed by Redis SET.

Kafka guarantees at-least-once delivery, meaning an event can be
re-delivered after a consumer crash. This module checks and marks
event_ids so a re-delivered event is silently skipped rather than
processed twice (which would cause double assignments).

TTL is set to 24 hours - enough to cover any realistic Kafka replay window.
"""

import redis as redis_lib

DEDUP_KEY = "processed_events"
DEDUP_TTL = 86400  # 24 hours in seconds


class DeduplicationCache:
    def __init__(self, redis_client: redis_lib.Redis):
        self.redis = redis_client

    def is_seen(self, event_id: str) -> bool:
        """Return True if this event has already been processed."""
        return self.redis.sismember(DEDUP_KEY, event_id)

    def mark_seen(self, event_id: str) -> None:
        """Mark event as processed and refresh TTL on the set."""
        self.redis.sadd(DEDUP_KEY, event_id)
        self.redis.expire(DEDUP_KEY, DEDUP_TTL)
