"""
services/kafka_producer.py
Kafka producer singleton for the API server.
Publishes ride_requests and driver_location events.
"""

import json
import os
import time
import uuid
from confluent_kafka import Producer

_producer = None


def get_producer() -> Producer:
    """Return a shared Kafka producer (lazy init)."""
    global _producer
    if _producer is None:
        _producer = Producer({
            "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            "acks": "all",               # wait for all replicas to confirm
            "retries": 3,
            "linger.ms": 5,              # small batching delay for throughput
        })
    return _producer


def publish_ride_request(ride_id: str, rider_id: str, region_id: str,
                          pickup_lat: float, pickup_lng: float,
                          dropoff_lat: float, dropoff_lng: float) -> None:
    """Publish a ride request event to the ride_requests topic."""
    event = {
        "event_id": str(uuid.uuid4()),
        "ride_id": ride_id,
        "rider_id": rider_id,
        "pickup_lat": pickup_lat,
        "pickup_lng": pickup_lng,
        "dropoff_lat": dropoff_lat,
        "dropoff_lng": dropoff_lng,
        "region_id": region_id,
        "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema_version": "1.0",
    }
    get_producer().produce(
        topic="ride_requests",
        key=region_id,
        value=json.dumps(event).encode("utf-8"),
    )
    get_producer().poll(0)  # trigger delivery callbacks without blocking


def publish_location_update(driver_id: str, region_id: str,
                             lat: float, lng: float, status: str,
                             heading: float = 0, speed_kmh: float = 0,
                             driver_name: str = "", vehicle_type: str = "SEDAN",
                             vehicle_no: str = "", rating: float = 5.0) -> None:
    """Publish a driver location update event."""
    event = {
        "event_id": str(uuid.uuid4()),
        "driver_id": driver_id,
        "lat": lat,
        "lng": lng,
        "heading": heading,
        "speed_kmh": speed_kmh,
        "status": status,
        "region_id": region_id,
        "timestamp": int(time.time()),
        "driver_name": driver_name,
        "vehicle_type": vehicle_type,
        "vehicle_no": vehicle_no,
        "rating": rating,
        "schema_version": "1.0",
    }
    get_producer().produce(
        topic="driver_location",
        key=region_id,
        value=json.dumps(event).encode("utf-8"),
    )
    get_producer().poll(0)
