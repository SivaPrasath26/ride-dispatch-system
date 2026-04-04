"""
routes/driver_routes.py
Driver-facing endpoints for publishing location and toggling availability.

POST  /api/v1/driver/location  - publish GPS update to Kafka
PATCH /api/v1/driver/status    - toggle AVAILABLE / OFFLINE
GET   /api/v1/driver/<id>      - get driver profile
"""

import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from services.redis_service import get_redis
from services.kafka_producer import publish_location_update
from utils.geo import get_region

driver_bp = Blueprint("driver", __name__)
log = logging.getLogger(__name__)


@driver_bp.post("/driver/location")
@jwt_required()
def update_location():
    """
    Publish driver location to Kafka.
    The location_consumer picks it up and updates Redis geo index.
    Returns immediately - no waiting for Redis write.
    """
    body = request.get_json()
    if not body:
        return jsonify({"error": "MISSING_BODY"}), 400

    driver_id = body.get("driver_id")
    lat = float(body.get("lat", 0))
    lng = float(body.get("lng", 0))
    status = body.get("status", "AVAILABLE")
    region_id = get_region(lat, lng)

    try:
        publish_location_update(
            driver_id=driver_id,
            region_id=region_id,
            lat=lat,
            lng=lng,
            status=status,
            heading=float(body.get("heading", 0)),
            speed_kmh=float(body.get("speed_kmh", 0)),
            driver_name=body.get("driver_name", ""),
            vehicle_type=body.get("vehicle_type", "SEDAN"),
            vehicle_no=body.get("vehicle_no", ""),
            rating=float(body.get("rating", 5.0)),
        )
    except Exception as e:
        log.error(f"[DriverRoutes] Failed to publish location: {e}")
        return jsonify({"error": "KAFKA_ERROR"}), 503

    return jsonify({"acknowledged": True}), 200


@driver_bp.patch("/driver/status")
@jwt_required()
def update_status():
    """
    Directly update driver availability in Redis.
    Used when driver goes offline or comes back online.
    """
    body = request.get_json()
    driver_id = body.get("driver_id")
    new_status = body.get("status")

    if new_status not in ("AVAILABLE", "OFFLINE", "BUSY"):
        return jsonify({"error": "INVALID_STATUS",
                        "message": "status must be AVAILABLE, OFFLINE, or BUSY"}), 422

    redis = get_redis()
    if not redis.exists(f"driver:{driver_id}"):
        return jsonify({"error": "DRIVER_NOT_FOUND"}), 404

    redis.hset(f"driver:{driver_id}", "status", new_status)

    return jsonify({"driver_id": driver_id, "status": new_status}), 200


@driver_bp.get("/driver/<driver_id>")
@jwt_required()
def get_driver(driver_id: str):
    """Return current driver state from Redis."""
    redis = get_redis()
    state = redis.hgetall(f"driver:{driver_id}")
    if not state:
        return jsonify({"error": "DRIVER_NOT_FOUND"}), 404
    state["driver_id"] = driver_id
    return jsonify(state), 200
