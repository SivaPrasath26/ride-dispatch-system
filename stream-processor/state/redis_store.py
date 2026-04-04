"""
state/redis_store.py
All Redis operations for the ride dispatch system.

Redis is the primary operational data store:
- Geo index for fast nearest-driver lookup (GEOADD / GEORADIUS)
- Driver state hash with TTL for automatic stale-driver eviction
- Assignment results served directly to the API
- Deduplication SET to prevent double-processing

The Lua script for atomic assignment is the critical correctness mechanism.
It runs atomically inside Redis - no other client can interleave between
the status check and the status update, preventing double assignment.
"""

import os
import time
import redis

# Lua script for atomic driver assignment (compare-and-swap).
# Returns 1 on success (driver was AVAILABLE and is now BUSY).
# Returns 0 on failure (driver was already BUSY - try next candidate).
ASSIGN_LUA = """
local driver_key = KEYS[1]
local ride_id = ARGV[1]
local current_status = redis.call('HGET', driver_key, 'status')
if current_status == 'AVAILABLE' then
    redis.call('HSET', driver_key, 'status', 'BUSY')
    redis.call('HSET', driver_key, 'current_ride_id', ride_id)
    return 1
else
    return 0
end
"""


class RedisStore:
    """Wraps all Redis operations with clear method names."""

    def __init__(self):
        pool = redis.ConnectionPool(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            max_connections=20,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=1,
            retry_on_timeout=True,
        )
        self.client = redis.Redis(connection_pool=pool)
        self._assign_script = self.client.register_script(ASSIGN_LUA)
        self.driver_ttl = int(os.getenv("DRIVER_TTL_SECONDS", 120))
        self.assignment_ttl = 300  # 5 minutes

    # ─── Geo Index ────────────────────────────────────────────────────────────

    def update_driver_position(self, region_id: str, driver_id: str,
                                lat: float, lng: float, state: dict) -> None:
        """
        Update driver geo position and state hash atomically using a pipeline.
        Pipeline batches GEOADD + HSET + EXPIRE into a single round-trip.
        """
        geo_key = f"drivers:geo:{region_id}"
        driver_key = f"driver:{driver_id}"

        pipe = self.client.pipeline()
        pipe.geoadd(geo_key, [lng, lat, driver_id])
        pipe.hset(driver_key, mapping={
            "lat": lat,
            "lng": lng,
            "status": state.get("status", "AVAILABLE"),
            "heading": state.get("heading", 0),
            "speed_kmh": state.get("speed_kmh", 0),
            "last_seen": int(time.time()),
            "region_id": region_id,
            "driver_name": state.get("driver_name", ""),
            "vehicle_type": state.get("vehicle_type", "SEDAN"),
            "vehicle_no": state.get("vehicle_no", ""),
            "rating": state.get("rating", 5.0),
        })
        pipe.expire(driver_key, self.driver_ttl)
        pipe.execute()

    def get_nearby_drivers(self, region_id: str, lat: float, lng: float,
                           radius_km: float, count: int = 20) -> list:
        """
        Return up to `count` driver IDs within `radius_km` of the pickup point,
        sorted by distance ascending.
        """
        geo_key = f"drivers:geo:{region_id}"
        results = self.client.georadius(
            geo_key, lng, lat, radius_km, "km",
            sort="ASC", count=count
        )
        return results or []

    # ─── Driver State ─────────────────────────────────────────────────────────

    def get_driver(self, driver_id: str) -> dict | None:
        """Return driver state hash or None if driver does not exist / TTL expired."""
        data = self.client.hgetall(f"driver:{driver_id}")
        return data if data else None

    def get_last_seen(self, driver_id: str) -> int:
        """Return the last_seen unix timestamp for late event detection."""
        val = self.client.hget(f"driver:{driver_id}", "last_seen")
        return int(val) if val else 0

    def free_driver(self, driver_id: str) -> None:
        """Mark driver as AVAILABLE again after ride completion."""
        self.client.hset(f"driver:{driver_id}", mapping={
            "status": "AVAILABLE",
            "current_ride_id": "",
        })

    # ─── Atomic Assignment ────────────────────────────────────────────────────

    def atomic_assign(self, driver_id: str, ride_id: str) -> bool:
        """
        Atomically assign a driver to a ride using the Lua CAS script.
        Returns True if assignment succeeded, False if driver was already taken.
        """
        result = self._assign_script(
            keys=[f"driver:{driver_id}"],
            args=[ride_id]
        )
        return result == 1

    # ─── Assignment Result ────────────────────────────────────────────────────

    def store_assignment(self, ride_id: str, driver_id: str,
                          driver_state: dict, distance_km: float) -> None:
        """Store assignment result in Redis for the API to serve."""
        eta_seconds = max(60, int((distance_km / 30) * 3600))  # approx at 30km/h
        self.client.hset(f"assignment:{ride_id}", mapping={
            "driver_id": driver_id,
            "driver_name": driver_state.get("driver_name", ""),
            "vehicle_type": driver_state.get("vehicle_type", "SEDAN"),
            "vehicle_no": driver_state.get("vehicle_no", ""),
            "rating": driver_state.get("rating", 5.0),
            "distance_km": round(distance_km, 2),
            "eta_seconds": eta_seconds,
            "assigned_at": int(time.time()),
        })
        self.client.expire(f"assignment:{ride_id}", self.assignment_ttl)

        # Update ride status in Redis
        self.client.hset(f"ride:{ride_id}", "status", "MATCHED")

    def store_ride(self, ride_id: str, rider_id: str, region_id: str,
                   pickup_lat: float, pickup_lng: float) -> None:
        """Store initial ride state in Redis when first created."""
        self.client.hset(f"ride:{ride_id}", mapping={
            "status": "SEARCHING",
            "rider_id": rider_id,
            "region_id": region_id,
            "pickup_lat": pickup_lat,
            "pickup_lng": pickup_lng,
            "created_at": int(time.time()),
        })
        self.client.expire(f"ride:{ride_id}", 3600)

    def get_assignment(self, ride_id: str) -> dict | None:
        """Return assignment details or None."""
        data = self.client.hgetall(f"assignment:{ride_id}")
        return data if data else None

    def get_ride_status(self, ride_id: str) -> str | None:
        """Return current ride status string or None."""
        return self.client.hget(f"ride:{ride_id}", "status")

    def set_ride_timeout(self, ride_id: str) -> None:
        """Mark ride as timed out - no driver found."""
        self.client.hset(f"ride:{ride_id}", "status", "TIMEOUT")

    def get_active_drivers(self, region_id: str = None, count: int = 200) -> list:
        """
        Return up to `count` active driver states for the frontend map.
        Scans all driver keys if no region is specified.
        """
        drivers = []
        pattern = "driver:*"
        for key in self.client.scan_iter(pattern, count=500):
            data = self.client.hgetall(key)
            if data and data.get("status") in ("AVAILABLE", "BUSY"):
                if region_id and data.get("region_id") != region_id:
                    continue
                data["driver_id"] = key.split(":", 1)[1]
                drivers.append(data)
                if len(drivers) >= count:
                    break
        return drivers
