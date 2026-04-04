"""
routes/ride_routes.py
Rider-facing endpoints for creating rides and polling assignment status.

POST /api/v1/ride         - create ride request (async, returns immediately)
GET  /api/v1/match/{id}  - poll for assignment result (reads Redis, sub-5ms)
POST /api/v1/ride/{id}/cancel
"""

import uuid
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from services.redis_service import get_redis
from services.kafka_producer import publish_ride_request
from utils.geo import get_region

ride_bp = Blueprint("ride", __name__)
log = logging.getLogger(__name__)


@ride_bp.post("/ride")
@jwt_required()
def create_ride():
    """
    Create a new ride request.
    Publishes to Kafka and returns ride_id immediately.
    The stream processor picks it up and writes the match result to Redis.
    """
    body = request.get_json()
    if not body:
        return jsonify({"error": "MISSING_BODY", "message": "Request body required"}), 400

    required = ["pickup_lat", "pickup_lng", "dropoff_lat", "dropoff_lng"]
    for field in required:
        if field not in body:
            return jsonify({"error": "MISSING_FIELD", "message": f"{field} required"}), 422

    pickup_lat = float(body["pickup_lat"])
    pickup_lng = float(body["pickup_lng"])
    region_id = get_region(pickup_lat, pickup_lng)
    ride_id = str(uuid.uuid4())

    # rider_id would normally come from JWT identity
    rider_id = body.get("rider_id", "anonymous")

    try:
        publish_ride_request(
            ride_id=ride_id,
            rider_id=rider_id,
            region_id=region_id,
            pickup_lat=pickup_lat,
            pickup_lng=pickup_lng,
            dropoff_lat=float(body["dropoff_lat"]),
            dropoff_lng=float(body["dropoff_lng"]),
        )
    except Exception as e:
        log.error(f"[RideRoutes] Failed to publish ride request: {e}")
        return jsonify({"error": "KAFKA_ERROR", "message": "Could not queue ride request"}), 503

    log.info(f"[RideRoutes] Created ride={ride_id} region={region_id}")

    return jsonify({
        "ride_id": ride_id,
        "status": "SEARCHING",
        "region_id": region_id,
    }), 202


@ride_bp.get("/match/<ride_id>")
@jwt_required()
def get_match(ride_id: str):
    """
    Poll for ride assignment result.
    All data served from Redis - no database query in this path.
    """
    redis = get_redis()

    assignment = redis.hgetall(f"assignment:{ride_id}")
    if assignment:
        return jsonify({
            "ride_id": ride_id,
            "status": "MATCHED",
            "driver": {
                "driver_id": assignment.get("driver_id"),
                "name": assignment.get("driver_name"),
                "vehicle_type": assignment.get("vehicle_type"),
                "vehicle_no": assignment.get("vehicle_no"),
                "rating": float(assignment.get("rating", 5.0)),
                "distance_km": float(assignment.get("distance_km", 0)),
                "eta_seconds": int(assignment.get("eta_seconds", 0)),
            }
        }), 200

    ride_status = redis.hget(f"ride:{ride_id}", "status")

    if ride_status == "TIMEOUT":
        return jsonify({"ride_id": ride_id, "status": "TIMEOUT"}), 200

    if ride_status == "CANCELLED":
        return jsonify({"ride_id": ride_id, "status": "CANCELLED"}), 200

    if ride_status == "SEARCHING" or ride_status is None:
        return jsonify({"ride_id": ride_id, "status": "SEARCHING"}), 200

    return jsonify({"ride_id": ride_id, "status": ride_status}), 200


@ride_bp.post("/ride/<ride_id>/cancel")
@jwt_required()
def cancel_ride(ride_id: str):
    """Cancel a ride that is still in SEARCHING state."""
    redis = get_redis()
    current_status = redis.hget(f"ride:{ride_id}", "status")

    if not current_status:
        return jsonify({"error": "RIDE_NOT_FOUND", "message": f"No ride found with id {ride_id}"}), 404

    if current_status not in ("SEARCHING", "MATCHED"):
        return jsonify({
            "error": "CANNOT_CANCEL",
            "message": f"Cannot cancel a ride with status {current_status}"
        }), 409

    redis.hset(f"ride:{ride_id}", "status", "CANCELLED")
    return jsonify({"ride_id": ride_id, "status": "CANCELLED"}), 200
