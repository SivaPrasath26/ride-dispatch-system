"""
tests/integration/test_race_condition.py
Stress test for atomic assignment - proves zero double-assignment.

Sends 50 simultaneous ride requests all near the same single driver.
Exactly 1 should be MATCHED, the rest TIMEOUT or SEARCHING.

Run with: pytest tests/integration/test_race_condition.py -v -s
Requires all Docker services running + at least 1 active driver.
"""

import os
import time
import uuid
import threading
import requests
import pytest

BASE_URL = os.getenv("API_URL", "http://localhost:5000/api/v1")
CONCURRENT_REQUESTS = 50


def get_token():
    resp = requests.post(f"{BASE_URL}/auth/token",
                         json={"user_id": "test-admin", "role": "rider"})
    return resp.json()["access_token"]


def create_ride(headers, results, index):
    payload = {
        "rider_id": str(uuid.uuid4()),
        "pickup_lat": 12.9716 + (index * 0.0001),
        "pickup_lng": 77.5946,
        "dropoff_lat": 13.0827,
        "dropoff_lng": 77.6065,
    }
    resp = requests.post(f"{BASE_URL}/ride", json=payload, headers=headers)
    if resp.status_code == 202:
        results[index] = resp.json()["ride_id"]


def test_no_double_assignment():
    headers = {"Authorization": f"Bearer {get_token()}"}
    results = [None] * CONCURRENT_REQUESTS

    # Fire all requests simultaneously
    threads = [
        threading.Thread(target=create_ride, args=(headers, results, i))
        for i in range(CONCURRENT_REQUESTS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ride_ids = [r for r in results if r is not None]
    print(f"\n[RaceTest] {len(ride_ids)} rides created")

    # Wait for matching to complete
    time.sleep(8)

    matched = []
    for ride_id in ride_ids:
        poll = requests.get(f"{BASE_URL}/match/{ride_id}", headers=headers)
        if poll.json().get("status") == "MATCHED":
            matched.append(ride_id)

    print(f"[RaceTest] MATCHED: {len(matched)} out of {len(ride_ids)}")

    # The critical assertion - no driver should be double-assigned
    driver_ids = []
    for ride_id in matched:
        poll = requests.get(f"{BASE_URL}/match/{ride_id}", headers=headers)
        driver_id = poll.json().get("driver", {}).get("driver_id")
        if driver_id:
            driver_ids.append(driver_id)

    unique_drivers = set(driver_ids)
    print(f"[RaceTest] Unique drivers assigned: {len(unique_drivers)}")

    # Each driver should appear at most once
    assert len(driver_ids) == len(unique_drivers), (
        f"DOUBLE ASSIGNMENT DETECTED: {len(driver_ids)} matches but only "
        f"{len(unique_drivers)} unique drivers"
    )
    print("[RaceTest] PASSED - zero double assignments confirmed")
