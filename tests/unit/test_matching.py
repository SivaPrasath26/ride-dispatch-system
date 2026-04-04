"""
tests/unit/test_matching.py
Unit tests for the ride matching logic using fakeredis.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../stream-processor"))

import fakeredis
import pytest
from unittest.mock import MagicMock, patch
from utils.dedup import DeduplicationCache
from handlers.ride_handler import RideHandler


@pytest.fixture
def fake_redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def setup_handler(fake_redis_client):
    from state.redis_store import RedisStore
    redis_store = MagicMock(spec=RedisStore)
    postgres_store = MagicMock()
    dedup = DeduplicationCache(fake_redis_client)
    handler = RideHandler(redis_store, postgres_store, dedup)
    return handler, redis_store, postgres_store


def test_duplicate_event_skipped(setup_handler):
    handler, redis_store, _ = setup_handler
    event = {
        "event_id": "dupe-001",
        "ride_id": "ride-001",
        "region_id": "BLR_SOUTH",
        "pickup_lat": 12.92,
        "pickup_lng": 77.60,
        "dropoff_lat": 12.95,
        "dropoff_lng": 77.62,
        "rider_id": "rider-001",
    }
    # Mark as seen first
    handler.dedup.mark_seen("dupe-001")
    handler.handle(event)
    # store_ride should never be called for a duplicate
    redis_store.store_ride.assert_not_called()


def test_no_drivers_causes_timeout(setup_handler):
    handler, redis_store, postgres_store = setup_handler
    redis_store.get_nearby_drivers.return_value = []
    redis_store.store_ride.return_value = None
    redis_store.set_ride_timeout.return_value = None

    event = {
        "event_id": "evt-002",
        "ride_id": "ride-002",
        "region_id": "BLR_SOUTH",
        "pickup_lat": 12.92,
        "pickup_lng": 77.60,
        "dropoff_lat": 12.95,
        "dropoff_lng": 77.62,
        "rider_id": "rider-002",
    }
    handler.handle(event)
    redis_store.set_ride_timeout.assert_called_once_with("ride-002")


def test_successful_match(setup_handler):
    handler, redis_store, postgres_store = setup_handler

    driver_state = {
        "lat": "12.921",
        "lng": "77.601",
        "status": "AVAILABLE",
        "driver_name": "Test Driver",
        "vehicle_type": "SEDAN",
        "vehicle_no": "KA01AB1234",
        "rating": "4.8",
    }
    redis_store.get_nearby_drivers.return_value = ["driver-abc"]
    redis_store.get_driver.return_value = driver_state
    redis_store.atomic_assign.return_value = True
    redis_store.store_ride.return_value = None
    redis_store.store_assignment.return_value = None

    event = {
        "event_id": "evt-003",
        "ride_id": "ride-003",
        "region_id": "BLR_SOUTH",
        "pickup_lat": 12.92,
        "pickup_lng": 77.60,
        "dropoff_lat": 12.95,
        "dropoff_lng": 77.62,
        "rider_id": "rider-003",
    }
    handler.handle(event)
    redis_store.store_assignment.assert_called_once()
    redis_store.set_ride_timeout.assert_not_called()


def test_driver_taken_falls_to_next(setup_handler):
    handler, redis_store, postgres_store = setup_handler

    driver_state = {
        "lat": "12.921", "lng": "77.601", "status": "AVAILABLE",
        "driver_name": "Driver A", "vehicle_type": "SEDAN",
        "vehicle_no": "KA01AB0001", "rating": "4.5",
    }
    driver_state_b = {
        "lat": "12.922", "lng": "77.602", "status": "AVAILABLE",
        "driver_name": "Driver B", "vehicle_type": "SEDAN",
        "vehicle_no": "KA01AB0002", "rating": "4.7",
    }
    redis_store.get_nearby_drivers.return_value = ["driver-a", "driver-b"]
    redis_store.get_driver.side_effect = [driver_state, driver_state_b]
    # First driver is taken, second succeeds
    redis_store.atomic_assign.side_effect = [False, True]
    redis_store.store_ride.return_value = None
    redis_store.store_assignment.return_value = None

    event = {
        "event_id": "evt-004",
        "ride_id": "ride-004",
        "region_id": "BLR_SOUTH",
        "pickup_lat": 12.92,
        "pickup_lng": 77.60,
        "dropoff_lat": 12.95,
        "dropoff_lng": 77.62,
        "rider_id": "rider-004",
    }
    handler.handle(event)
    assert redis_store.atomic_assign.call_count == 2
    redis_store.store_assignment.assert_called_once()
