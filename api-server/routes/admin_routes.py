"""
routes/admin_routes.py
Admin and system endpoints.

GET  /admin/drivers/active  - live driver positions for frontend map
GET  /metrics/summary       - system metrics for admin dashboard
POST /auth/token            - dev-only token generation (remove in production)
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.redis_service import get_redis
from services.auth_service import verify_token, generate_token

router = APIRouter(tags=["admin"])
log = logging.getLogger(__name__)


class TokenRequest(BaseModel):
    user_id: str = "test-user"
    role: str = "rider"


@router.get("/admin/drivers/active")
def active_drivers(
    current_user: Annotated[dict, Depends(verify_token)],
):
    """
    Return up to 200 active driver positions for the frontend Leaflet map.
    Scans Redis driver keys - polled every 2 seconds by the frontend.
    """
    redis = get_redis()
    drivers = []

    for key in redis.scan_iter("driver:*", count=500):
        data = redis.hgetall(key)
        if data and data.get("status") in ("AVAILABLE", "BUSY"):
            drivers.append({
                "driver_id":    key.split(":", 1)[1],
                "lat":          float(data.get("lat", 0)),
                "lng":          float(data.get("lng", 0)),
                "status":       data.get("status"),
                "heading":      float(data.get("heading", 0)),
                "vehicle_type": data.get("vehicle_type", "SEDAN"),
            })
        if len(drivers) >= 200:
            break

    return {"drivers": drivers, "count": len(drivers)}


@router.get("/metrics/summary")
def metrics_summary(
    current_user: Annotated[dict, Depends(verify_token)],
):
    """
    Lightweight metrics for the frontend admin dashboard.
    Full observability is in Prometheus at :9090 and Grafana at :3001.
    """
    redis = get_redis()
    available = 0
    for key in redis.scan_iter("driver:*", count=500):
        if redis.hget(key, "status") == "AVAILABLE":
            available += 1

    return {
        "active_drivers": available,
        "note": "Full metrics at Prometheus :9090 and Grafana :3001",
    }


@router.post("/auth/token")
def get_token(body: TokenRequest):
    """
    Dev-only endpoint to generate a JWT for testing.
    No auth required - remove or protect this in production.
    """
    token = generate_token(body.user_id, body.role)
    return {"access_token": token}
