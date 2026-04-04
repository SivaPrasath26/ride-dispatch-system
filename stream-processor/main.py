"""
main.py - Stream Processor entry point.

Starts two consumer threads:
1. ride_consumer   - matching engine for ride_requests topic
2. location_consumer - state updater for driver_location topic

Both share the same Redis and PostgreSQL connection pools.
Prometheus metrics server starts on port 8001.
"""

import logging
import threading
import os

import redis as redis_lib

from state.redis_store import RedisStore
from state.postgres_store import PostgresStore
from utils.dedup import DeduplicationCache
from utils.metrics import start_metrics_server
from handlers.ride_handler import RideHandler
from handlers.location_handler import LocationHandler
from consumers.ride_consumer import run_ride_consumer
from consumers.location_consumer import run_location_consumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger(__name__)


def main():
    log.info("[Main] Starting stream processor")

    # Shared state stores
    redis_store = RedisStore()
    postgres_store = PostgresStore()

    # Shared dedup cache backed by Redis
    redis_client = redis_lib.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True
    )
    dedup = DeduplicationCache(redis_client)

    # Wire up handlers
    ride_handler = RideHandler(redis_store, postgres_store, dedup)
    location_handler = LocationHandler(redis_store, dedup)

    # Start Prometheus metrics server
    start_metrics_server()

    # Start both consumers in separate daemon threads
    ride_thread = threading.Thread(
        target=run_ride_consumer,
        args=(ride_handler,),
        name="ride-consumer",
        daemon=True
    )
    location_thread = threading.Thread(
        target=run_location_consumer,
        args=(location_handler,),
        name="location-consumer",
        daemon=True
    )

    ride_thread.start()
    location_thread.start()

    log.info("[Main] Both consumers running. Waiting...")

    # Keep main thread alive
    ride_thread.join()
    location_thread.join()


if __name__ == "__main__":
    main()
