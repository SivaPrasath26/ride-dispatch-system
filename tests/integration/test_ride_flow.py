"""
tests/integration/test_ride_flow.py
End-to-end ride flow integration test.
Requires all Docker services to be running.

Run with: pytest tests/integration/test_ride_flow.py -v
"""

import os
import time
import uuid
import requests
import pytest

BASE_URL = os.getenv("API_URL", "http://localhost:5000/api/v1")


def get_token():
    resp = requests.post(f"{BASE_URL}/auth/token",
                         json={"user_id": "test-rider", "role": "rider"})
    return resp.json()["access_token"]


@pytest.fixture
def headers():
    return {"Authorization": f"Bearer {get_token()}"}


def test_health_check():
    resp = requests.get(f"{BASE_URL}/health")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("healthy", "degraded")


def test_create_ride_returns_202(headers):
    payload = {
        "rider_id": str(uuid.uuid4()),
        "pickup_lat": 12.9716,
        "pickup_lng": 77.5946,
        "dropoff_lat": 13.0827,
        "dropoff_lng": 77.6065,
    }
    resp = requests.post(f"{BASE_URL}/ride", json=payload, headers=headers)
    assert resp.status_code == 202
    data = resp.json()
    assert "ride_id" in data
    assert data["status"] == "SEARCHING"


def test_poll_match_returns_status(headers):
    payload = {
        "rider_id": str(uuid.uuid4()),
        "pickup_lat": 12.9716,
        "pickup_lng": 77.5946,
        "dropoff_lat": 13.0827,
        "dropoff_lng": 77.6065,
    }
    resp = requests.post(f"{BASE_URL}/ride", json=payload, headers=headers)
    ride_id = resp.json()["ride_id"]

    # Poll for up to 10 seconds
    for _ in range(10):
        time.sleep(1)
        poll = requests.get(f"{BASE_URL}/match/{ride_id}", headers=headers)
        assert poll.status_code == 200
        status = poll.json()["status"]
        if status in ("MATCHED", "TIMEOUT"):
            break

    assert status in ("MATCHED", "TIMEOUT", "SEARCHING")


def test_cancel_ride(headers):
    payload = {
        "rider_id": str(uuid.uuid4()),
        "pickup_lat": 12.9716,
        "pickup_lng": 77.5946,
        "dropoff_lat": 13.0827,
        "dropoff_lng": 77.6065,
    }
    resp = requests.post(f"{BASE_URL}/ride", json=payload, headers=headers)
    ride_id = resp.json()["ride_id"]

    cancel = requests.post(f"{BASE_URL}/ride/{ride_id}/cancel", headers=headers)
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "CANCELLED"
