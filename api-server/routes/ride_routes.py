"""
routes/ride_routes.py
Rider-facing endpoints.

POST /ride              - create ride request (async, returns immediately)
GET  /match/{ride_id}  - poll assignment result (Redis only, sub-5ms)
POST /ride/{id}/cancel - cancel a searching or matched ride
"""

import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from services.redis_service import get_redis
from services.kafka_producer import publish_ride_request
from services.auth_service import verify_token
from utils.geo import get_region

router = APIRouter(tags=["ride"])
log = logging.getLogger(__name__)


# ─── Request / Response models ────────────────────────────────────────────────

class RideRequest(BaseModel):
    rider_id: str
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/ride", status_code=202)
def create_ride(
    body: RideRequest,
    current_user: Annotated[dict, Depends(verify_token)],
):
    """
    Create a new ride request.
    Publishes to Kafka and returns ride_id immediately - matching is async.
    The stream processor assigns a driver and writes the result to Redis.
    The rider polls GET /match/{ride_id} for the result.
    """
    region_id = get_region(body.pickup_lat, body.pickup_lng)
    ride_id = str(uuid.uuid4())

    try:
        publish_ride_request(
            ride_id=ride_id,
            rider_id=body.rider_id,
            region_id=region_id,
            pickup_lat=body.pickup_lat,
            pickup_lng=body.pickup_lng,
            dropoff_lat=body.dropoff_lat,
            dropoff_lng=body.dropoff_lng,
        )
    except Exception as e:
        log.error(f"[RideRoutes] Kafka publish failed: {e}")
        raise HTTPException(status_code=503, detail="Could not queue ride request")

    log.info(f"[RideRoutes] Created ride={ride_id} region={region_id}")
    return {"ride_id": ride_id, "status": "SEARCHING", "region_id": region_id}


@router.get("/match/{ride_id}")
def get_match(
    ride_id: str,
    current_user: Annotated[dict, Depends(verify_token)],
):
    """
    Poll for assignment result.
    Served entirely from Redis - no database query in this path.
    """
    redis = get_redis()

    assignment = redis.hgetall(f"assignment:{ride_id}")
    if assignment:
        return {
            "ride_id": ride_id,
            "status": "MATCHED",
            "driver": {
                "driver_id":   assignment.get("driver_id"),
                "name":        assignment.get("driver_name"),
                "vehicle_type": assignment.get("vehicle_type"),
                "vehicle_no":  assignment.get("vehicle_no"),
                "rating":      float(assignment.get("rating", 5.0)),
                "distance_km": float(assignment.get("distance_km", 0)),
                "eta_seconds": int(assignment.get("eta_seconds", 0)),
            },
        }

    ride_status = redis.hget(f"ride:{ride_id}", "status")

    if ride_status in ("TIMEOUT", "CANCELLED"):
        return {"ride_id": ride_id, "status": ride_status}

    return {"ride_id": ride_id, "status": ride_status or "SEARCHING"}


@router.post("/ride/{ride_id}/cancel")
def cancel_ride(
    ride_id: str,
    current_user: Annotated[dict, Depends(verify_token)],
):
    """Cancel a ride that is still SEARCHING or MATCHED."""
    redis = get_redis()
    current_status = redis.hget(f"ride:{ride_id}", "status")

    if not current_status:
        raise HTTPException(status_code=404, detail=f"Ride {ride_id} not found")

    if current_status not in ("SEARCHING", "MATCHED"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel ride with status {current_status}",
        )

    redis.hset(f"ride:{ride_id}", "status", "CANCELLED")
    return {"ride_id": ride_id, "status": "CANCELLED"}
