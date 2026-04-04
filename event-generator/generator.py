"""
event-generator/generator.py
Simulates riders and drivers producing realistic Kafka events.

Drivers:
- Start at random positions across Bangalore city grid
- Move slowly in a random direction every 5 seconds
- Occasionally go OFFLINE and come back AVAILABLE

Riders:
- Generated at a configurable rate (default 10/sec)
- Random pickup and dropoff within city bounds
"""

import json
import math
import os
import random
import time
import uuid
from confluent_kafka import Producer

# ─── Config ───────────────────────────────────────────────────────────────────

KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
NUM_DRIVERS = int(os.getenv("NUM_DRIVERS", 200))
RIDE_RATE = float(os.getenv("RIDE_RATE_PER_SEC", 10))

# Bangalore bounding box
LAT_MIN, LAT_MAX = 12.85, 13.15
LNG_MIN, LNG_MAX = 77.35, 77.85

REGIONS = {
    "BLR_NORTH":   (13.07, 77.60),
    "BLR_SOUTH":   (12.92, 77.60),
    "BLR_EAST":    (12.97, 77.77),
    "BLR_WEST":    (12.97, 77.42),
    "BLR_CENTRAL": (13.00, 77.60),
}

VEHICLE_TYPES = ["SEDAN", "SUV", "AUTO", "HATCHBACK"]
DRIVER_NAMES = [
    "Ravi Kumar", "Suresh Babu", "Mohan Das", "Arjun Singh",
    "Kiran Reddy", "Vijay Nair", "Ramesh Pillai", "Deepak Sharma",
    "Santosh Rao", "Anand Krishnan", "Pradeep Joshi", "Manoj Verma",
]


def random_coord():
    return (
        round(random.uniform(LAT_MIN, LAT_MAX), 6),
        round(random.uniform(LNG_MIN, LNG_MAX), 6),
    )


def get_region(lat, lng):
    if lat >= 13.00:
        return "BLR_NORTH"
    if lat < 12.95:
        return "BLR_SOUTH"
    if lng >= 77.70:
        return "BLR_EAST"
    if lng <= 77.50:
        return "BLR_WEST"
    return "BLR_CENTRAL"


def move(lat, lng, heading, speed_kmh=30):
    """Simulate movement: advance position by ~5 seconds of travel."""
    distance_km = speed_kmh * (5 / 3600)
    dlat = (distance_km / 111) * math.cos(math.radians(heading))
    dlng = (distance_km / (111 * math.cos(math.radians(lat)))) * math.sin(math.radians(heading))
    lat = max(LAT_MIN, min(LAT_MAX, lat + dlat))
    lng = max(LNG_MIN, min(LNG_MAX, lng + dlng))
    return round(lat, 6), round(lng, 6)


class Driver:
    def __init__(self, driver_id):
        self.driver_id = driver_id
        self.lat, self.lng = random_coord()
        self.heading = random.uniform(0, 360)
        self.speed_kmh = random.uniform(10, 50)
        self.status = "AVAILABLE"
        self.name = random.choice(DRIVER_NAMES)
        self.vehicle_type = random.choice(VEHICLE_TYPES)
        self.vehicle_no = f"KA{random.randint(1,99):02d}AB{random.randint(1000,9999)}"
        self.rating = round(random.uniform(3.8, 5.0), 1)
        self.offline_counter = 0

    def tick(self):
        """Advance driver state by one 5-second tick."""
        # Occasionally change direction
        if random.random() < 0.1:
            self.heading = random.uniform(0, 360)

        # Occasionally go offline briefly
        if self.status == "AVAILABLE" and random.random() < 0.02:
            self.status = "OFFLINE"
            self.offline_counter = random.randint(2, 6)
        elif self.status == "OFFLINE":
            self.offline_counter -= 1
            if self.offline_counter <= 0:
                self.status = "AVAILABLE"

        if self.status != "OFFLINE":
            self.lat, self.lng = move(self.lat, self.lng, self.heading, self.speed_kmh)

    def to_event(self):
        return {
            "event_id": str(uuid.uuid4()),
            "driver_id": self.driver_id,
            "lat": self.lat,
            "lng": self.lng,
            "heading": round(self.heading, 1),
            "speed_kmh": round(self.speed_kmh, 1),
            "status": self.status,
            "region_id": get_region(self.lat, self.lng),
            "timestamp": int(time.time()),
            "driver_name": self.name,
            "vehicle_type": self.vehicle_type,
            "vehicle_no": self.vehicle_no,
            "rating": self.rating,
            "schema_version": "1.0",
        }


def make_ride_event():
    pickup_lat, pickup_lng = random_coord()
    dropoff_lat, dropoff_lng = random_coord()
    return {
        "event_id": str(uuid.uuid4()),
        "ride_id": str(uuid.uuid4()),
        "rider_id": str(uuid.uuid4()),
        "pickup_lat": pickup_lat,
        "pickup_lng": pickup_lng,
        "dropoff_lat": dropoff_lat,
        "dropoff_lng": dropoff_lng,
        "region_id": get_region(pickup_lat, pickup_lng),
        "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema_version": "1.0",
    }


def main():
    print(f"[Generator] Starting with {NUM_DRIVERS} drivers, {RIDE_RATE} rides/sec")

    producer = Producer({
        "bootstrap.servers": KAFKA_SERVERS,
        "acks": 1,
        "linger.ms": 10,
    })

    # Initialise driver fleet
    drivers = [Driver(str(uuid.uuid4())) for _ in range(NUM_DRIVERS)]

    ride_interval = 1.0 / RIDE_RATE
    last_ride_ts = 0
    tick = 0

    while True:
        loop_start = time.time()

        # ── Location updates every 5 seconds ──────────────────────────────────
        if tick % 5 == 0:
            for driver in drivers:
                driver.tick()
                event = driver.to_event()
                producer.produce(
                    topic="driver_location",
                    key=event["region_id"],
                    value=json.dumps(event).encode(),
                )
            producer.poll(0)
            print(f"[Generator] tick={tick} published {NUM_DRIVERS} location updates")

        # ── Ride requests at configured rate ──────────────────────────────────
        now = time.time()
        if now - last_ride_ts >= ride_interval:
            event = make_ride_event()
            producer.produce(
                topic="ride_requests",
                key=event["region_id"],
                value=json.dumps(event).encode(),
            )
            producer.poll(0)
            last_ride_ts = now

        tick += 1
        elapsed = time.time() - loop_start
        time.sleep(max(0, 1.0 - elapsed))


if __name__ == "__main__":
    main()
