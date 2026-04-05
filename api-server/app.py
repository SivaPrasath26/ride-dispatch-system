"""
app.py - FastAPI application entry point.

Mounts three routers:
  /api/v1/ride*     - rider endpoints
  /api/v1/driver*   - driver endpoints
  /api/v1/admin*    - admin + auth endpoints

All matching reads are served from Redis (sub-5ms).
PostgreSQL is only hit for historical data - never in the critical path.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.ride_routes import router as ride_router
from routes.driver_routes import router as driver_router
from routes.admin_routes import router as admin_router
from services.redis_service import get_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - verify Redis is reachable
    try:
        get_redis().ping()
        print("[Startup] Redis connected")
    except Exception as e:
        print(f"[Startup] Redis connection failed: {e}")
    yield
    # Shutdown - nothing to clean up


app = FastAPI(
    title="Ride Dispatch System",
    description="Real-time ride matching API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(ride_router,   prefix="/api/v1")
app.include_router(driver_router, prefix="/api/v1")
app.include_router(admin_router,  prefix="/api/v1")


@app.get("/api/v1/health", tags=["system"])
def health():
    """Health check - no auth required."""
    redis_ok = False
    try:
        get_redis().ping()
        redis_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if redis_ok else "degraded",
        "redis": "connected" if redis_ok else "error",
    }
