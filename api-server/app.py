"""
app.py - Flask API Server entry point.

Exposes REST endpoints for riders, drivers, and admin.
All matching reads come from Redis (sub-5ms).
PostgreSQL is only queried for historical data (ride history, profiles).
"""

import os
import logging
from flask import Flask
from flask_jwt_extended import JWTManager
from flask_cors import CORS

from routes.ride_routes import ride_bp
from routes.driver_routes import driver_bp
from routes.admin_routes import admin_bp
from services.redis_service import get_redis
from services.kafka_producer import get_producer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)


def create_app() -> Flask:
    app = Flask(__name__)

    # ── Config ────────────────────────────────────────────────────────────────
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False  # long-lived for dev

    # ── Extensions ────────────────────────────────────────────────────────────
    JWTManager(app)
    CORS(app)

    # ── Blueprints ────────────────────────────────────────────────────────────
    app.register_blueprint(ride_bp,   url_prefix="/api/v1")
    app.register_blueprint(driver_bp, url_prefix="/api/v1")
    app.register_blueprint(admin_bp,  url_prefix="/api/v1")

    # ── Health check (no auth) ────────────────────────────────────────────────
    @app.get("/api/v1/health")
    def health():
        redis_ok = False
        try:
            get_redis().ping()
            redis_ok = True
        except Exception:
            pass

        return {
            "status": "healthy" if redis_ok else "degraded",
            "redis": "connected" if redis_ok else "error",
        }, 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_ENV") == "development")
