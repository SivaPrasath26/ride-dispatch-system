"""
tests/unit/test_geo.py
Unit tests for the Haversine distance calculation and region lookup.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../stream-processor"))

import pytest
from utils.geo import haversine_km, get_region


def test_haversine_same_point():
    assert haversine_km(12.9716, 77.5946, 12.9716, 77.5946) == pytest.approx(0.0, abs=0.001)


def test_haversine_known_distance():
    # Bangalore to Mysore is roughly 145 km
    dist = haversine_km(12.9716, 77.5946, 12.2958, 76.6394)
    assert 140 < dist < 155


def test_haversine_short_distance():
    # 1km north approximately
    dist = haversine_km(12.9716, 77.5946, 12.9806, 77.5946)
    assert 0.9 < dist < 1.1


def test_get_region_south():
    assert get_region(12.92, 77.60) == "BLR_SOUTH"


def test_get_region_north():
    assert get_region(13.05, 77.60) == "BLR_NORTH"


def test_get_region_central():
    assert get_region(13.00, 77.60) == "BLR_CENTRAL"


def test_get_region_fallback():
    # Outside all defined regions - should fall back to default
    result = get_region(10.0, 75.0)
    assert result == "BLR_SOUTH"
