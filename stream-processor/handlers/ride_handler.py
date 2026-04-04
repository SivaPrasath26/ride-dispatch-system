"""
handlers/ride_handler.py
Core matching engine - processes ride_requests Kafka events.

Flow for each event:
1. Deduplication check - skip if already processed
2. GEORADIUS - fetch nearest drivers
3. Filter by AVAILABLE status
4. Haversine sort - confirm nearest
5. Atomic Lua assignment - prevents double booking
6. Store result in Redis for API to serve
7. Async write to PostgreSQL
8. Commit Kafka offset
"""

import os
import time
import threading
import logging

from utils.geo import haversine_km, adjacent_regions
from utils.dedup import DeduplicationCache
from utils import metrics as m

log = logging.getLogger(__name__)

# Retry radius steps in km. System tries each step before giving up.
RADIUS_STEPS = [int(os.getenv("MATCHING_RADIUS_KM", 5)), 7, 10, 15]
MATCH_TIMEOUT = int(os.getenv("MATCH_TIMEOUT_SECONDS", 30))

class RideHandler:
    def __init__(self, redis_store, postgres_store, dedup: DeduplicationCache):
        self.redis = redis_store
        self.pg = postgres_store
        self.dedup = dedup

    def handle(self, event: dict) -> None:
        """
        Process a single ride_requests event.
        This is called from the Kafka consumer loop.
        """
        event_id = event.get("event_id", "")
        ride_id = event.get("ride_id", "")
        region_id = event.get("region_id", "BLR_SOUTH")

        m.ride_requests_total.labels(region_id=region_id).inc()

        # ── 1. Deduplication ─────────────────────────────────────────────────
        if self.dedup.is_seen(event_id):
            m.duplicate_events_skipped_total.labels(topic="ride_requests").inc()
            log.debug(f"[RideHandler] Skipping duplicate event {event_id}")
            return

        start_ts = time.time()

        pickup_lat = float(event["pickup_lat"])
        pickup_lng = float(event["pickup_lng"])

        # Store ride as SEARCHING in Redis so the API can respond immediately
        self.redis.store_ride(
            ride_id=ride_id,
            rider_id=event.get("rider_id", ""),
            region_id=region_id,
            pickup_lat=pickup_lat,
            pickup_lng=pickup_lng,
        )

        # Async save to PostgreSQL - does not block matching
        threading.Thread(
            target=self.pg.save_ride,
            args=(ride_id, event.get("rider_id", ""), region_id,
                  pickup_lat, pickup_lng,
                  event.get("dropoff_lat"), event.get("dropoff_lng")),
            daemon=True,
        ).start()

        # ── 2-5. Match and assign ─────────────────────────────────────────────
        assigned = self._try_match(ride_id, region_id, pickup_lat, pickup_lng)

        if assigned:
            driver_id, driver_state, distance_km = assigned
            latency_ms = int((time.time() - start_ts) * 1000)

            # Store assignment in Redis for the API
            self.redis.store_assignment(ride_id, driver_id, driver_state, distance_km)

            m.rides_matched_total.labels(region_id=region_id).inc()
            m.matching_latency_ms.labels(region_id=region_id).observe(latency_ms)

            log.info(
                f"[RideHandler] MATCHED ride={ride_id} driver={driver_id} "
                f"dist={distance_km:.2f}km latency={latency_ms}ms"
            )

            # Async PostgreSQL update
            threading.Thread(
                target=self.pg.update_ride_matched,
                args=(ride_id, driver_id, distance_km, latency_ms),
                daemon=True,
            ).start()
        else:
            # No driver found in any radius - mark as timeout
            self.redis.set_ride_timeout(ride_id)
            m.rides_timeout_total.labels(region_id=region_id).inc()
            log.warning(f"[RideHandler] TIMEOUT ride={ride_id} region={region_id}")

            threading.Thread(
                target=self.pg.update_ride_timeout,
                args=(ride_id,),
                daemon=True,
            ).start()

        # ── 6. Mark event processed ────────────────────────────────────────────
        self.dedup.mark_seen(event_id)

    def _try_match(self, ride_id: str, region_id: str,
                   pickup_lat: float, pickup_lng: float):
        """
        Try to assign a driver using expanding radius steps.
        Also checks adjacent regions if primary region returns no candidates.
        Returns (driver_id, driver_state, distance_km) or None.
        """
        regions_to_try = [region_id] + adjacent_regions(region_id)

        for radius_km in RADIUS_STEPS:
            for region in regions_to_try:
                result = self._match_in_region(
                    ride_id, region, pickup_lat, pickup_lng, radius_km
                )
                if result:
                    return result

        return None

    def _match_in_region(self, ride_id: str, region_id: str,
                          pickup_lat: float, pickup_lng: float, radius_km: float):
        """
        Fetch candidates from Redis geo index, filter available drivers,
        and atomically assign the nearest one.
        """
        t0 = time.time()
        candidates = self.redis.get_nearby_drivers(
            region_id, pickup_lat, pickup_lng, radius_km, count=20
        )
        m.georadius_latency_ms.observe((time.time() - t0) * 1000)

        if not candidates:
            return None

        # Fetch full state and filter to AVAILABLE drivers only
        available = []
        for driver_id in candidates:
            state = self.redis.get_driver(driver_id)
            if state and state.get("status") == "AVAILABLE":
                dist = haversine_km(
                    pickup_lat, pickup_lng,
                    float(state["lat"]), float(state["lng"])
                )
                available.append((dist, driver_id, state))

        if not available:
            return None

        # Sort by distance - nearest first
        available.sort(key=lambda x: x[0])

        # Try atomic assignment on candidates until one succeeds
        for distance_km, driver_id, driver_state in available:
            success = self.redis.atomic_assign(driver_id, ride_id)
            m.assignment_attempts_total.labels(
                result="success" if success else "failure"
            ).inc()
            if success:
                return driver_id, driver_state, distance_km

        return None
