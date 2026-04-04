"""
routes/admin_routes.py
Admin and system endpoints.

GET /api/v1/admin/drivers/active  - live driver positions for frontend map
GET /api/v1/metrics/summary       - system metrics for admin dashboard
POST /api/v1/auth/token           - dev-only token generation
"""

import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from services.redis_service import get_redis
from services.auth_service import generate_token

admin_bp = Blueprint("admin", __name__)
log = logging.getLogger(__name__)


@admin_bp.get("/admin/drivers/active")
@jwt_required()
def active_drivers():
    """
    Return up to 200 active driver positions for the frontend map.
    Scans Redis driver keys and returns lat/lng/status for each.
    Polled by the frontend every 2 seconds.
    """
    redis = get_redis()
    drivers = []

    for key in redis.scan_iter("driver:*", count=500):
        data = redis.hgetall(key)
        if data and data.get("status") in ("AVAILABLE", "BUSY"):
            drivers.append({
                "driver_id": key.split(":", 1)[1],
                "lat": float(data.get("lat", 0)),
                "lng": float(data.get("lng", 0)),
                "status": data.get("status"),
                "heading": float(data.get("heading", 0)),
                "vehicle_type": data.get("vehicle_type", "SEDAN"),
            })
        if len(drivers) >= 200:
            break

    return jsonify({"drivers": drivers, "count": len(drivers)}), 200


@admin_bp.get("/metrics/summary")
@jwt_required()
def metrics_summary():
    """
    Aggregated system metrics for the frontend admin dashboard.
    Reads lightweight counters from Redis.
    """
    redis = get_redis()

    active_count = 0
    for key in redis.scan_iter("driver:*", count=500):
        status = redis.hget(key, "status")
        if status == "AVAILABLE":
            active_count += 1

    return jsonify({
        "active_drivers": active_count,
        "note": "For full metrics see Prometheus at :9090 and Grafana at :3001"
    }), 200


@admin_bp.post("/auth/token")
def get_token():
    """
    Dev-only endpoint to generate a JWT token for testing.
    Remove or protect this in production.
    """
    body = request.get_json() or {}
    user_id = body.get("user_id", "test-user")
    role = body.get("role", "rider")
    token = generate_token(user_id, role)
    return jsonify({"access_token": token}), 200
