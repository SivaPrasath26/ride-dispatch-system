"""
handlers/location_handler.py
Processes driver_location Kafka events.

Each driver app sends its GPS coordinates every 5 seconds.
This handler:
1. Checks for late events (out-of-order delivery) and discards them
2. Updates the Redis geo index and driver state hash
3. Refreshes the driver TTL so inactive drivers auto-expire
"""

import logging
from utils.dedup import DeduplicationCache
from utils import metrics as m

log = logging.getLogger(__name__)


class LocationHandler:
    def __init__(self, redis_store, dedup: DeduplicationCache):
        self.redis = redis_store
        self.dedup = dedup

    def handle(self, event: dict) -> None:
        """Process a single driver_location event."""
        event_id = event.get("event_id", "")
        driver_id = event.get("driver_id", "")
        region_id = event.get("region_id", "BLR_SOUTH")

        # ── 1. Deduplication ─────────────────────────────────────────────────
        if self.dedup.is_seen(event_id):
            m.duplicate_events_skipped_total.labels(topic="driver_location").inc()
            return

        # ── 2. Late event detection ────────────────────────────────────────────
        # If the incoming event timestamp is older than what we already have
        # stored, discard it. A delayed network packet should never overwrite
        # a more recent known position.
        event_ts = int(event.get("timestamp", 0))
        stored_ts = self.redis.get_last_seen(driver_id)

        if stored_ts and event_ts < stored_ts:
            m.late_events_dropped_total.labels(region_id=region_id).inc()
            log.debug(
                f"[LocationHandler] Dropped late event for driver={driver_id} "
                f"event_ts={event_ts} stored_ts={stored_ts}"
            )
            return

        # ── 3. Update Redis state ──────────────────────────────────────────────
        lat = float(event["lat"])
        lng = float(event["lng"])

        self.redis.update_driver_position(
            region_id=region_id,
            driver_id=driver_id,
            lat=lat,
            lng=lng,
            state={
                "status": event.get("status", "AVAILABLE"),
                "heading": event.get("heading", 0),
                "speed_kmh": event.get("speed_kmh", 0),
                "driver_name": event.get("driver_name", ""),
                "vehicle_type": event.get("vehicle_type", "SEDAN"),
                "vehicle_no": event.get("vehicle_no", ""),
                "rating": event.get("rating", 5.0),
            }
        )

        log.debug(
            f"[LocationHandler] Updated driver={driver_id} "
            f"lat={lat} lng={lng} status={event.get('status')}"
        )

        self.dedup.mark_seen(event_id)
