"""
routes/driver_routes.py
Driver-facing endpoints.

POST  /driver/location  - publish GPS update to Kafka
PATCH /driver/status    - toggle AVAILABLE / OFFLINE
GET   /driver/{id}      - get live driver state from Redis
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.redis_service import get_redis
from services.kafka_producer import publish_location_update
from services.auth_service import verify_token
from utils.geo import get_region

router = APIRouter(tags=["driver"])
log = logging.getLogger(__name__)


# ─── Request models ───────────────────────────────────────────────────────────

class LocationUpdate(BaseModel):
    driver_id: str
    lat: float
    lng: float
    status: str = "AVAILABLE"
    heading: float = 0
    speed_kmh: float = 0
    driver_name: str = ""
    vehicle_type: str = "SEDAN"
    vehicle_no: str = ""
    rating: float = 5.0


class StatusUpdate(BaseModel):
    driver_id: str
    status: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/driver/location")
def update_location(
    body: LocationUpdate,
    current_user: Annotated[dict, Depends(verify_token)],
):
    """
    Publish driver GPS update to Kafka.
    The location_consumer picks it up and updates the Redis geo index.
    Returns immediately - does not wait for Redis write.
    """
    region_id = get_region(body.lat, body.lng)
    try:
        publish_location_update(
            driver_id=body.driver_id,
            region_id=region_id,
            lat=body.lat,
            lng=body.lng,
            status=body.status,
            heading=body.heading,
            speed_kmh=body.speed_kmh,
            driver_name=body.driver_name,
            vehicle_type=body.vehicle_type,
            vehicle_no=body.vehicle_no,
            rating=body.rating,
        )
    except Exception as e:
        log.error(f"[DriverRoutes] Kafka publish failed: {e}")
        raise HTTPException(status_code=503, detail="Could not publish location")

    return {"acknowledged": True}


@router.patch("/driver/status")
def update_status(
    body: StatusUpdate,
    current_user: Annotated[dict, Depends(verify_token)],
):
    """
    Directly update driver availability in Redis.
    Used when driver goes offline or comes back online.
    """
    if body.status not in ("AVAILABLE", "OFFLINE", "BUSY"):
        raise HTTPException(
            status_code=422,
            detail="status must be AVAILABLE, OFFLINE, or BUSY",
        )

    redis = get_redis()
    if not redis.exists(f"driver:{body.driver_id}"):
        raise HTTPException(status_code=404, detail="Driver not found")

    redis.hset(f"driver:{body.driver_id}", "status", body.status)
    return {"driver_id": body.driver_id, "status": body.status}


@router.get("/driver/{driver_id}")
def get_driver(
    driver_id: str,
    current_user: Annotated[dict, Depends(verify_token)],
):
    """Return current driver state from Redis."""
    state = get_redis().hgetall(f"driver:{driver_id}")
    if not state:
        raise HTTPException(status_code=404, detail="Driver not found")
    state["driver_id"] = driver_id
    return state
