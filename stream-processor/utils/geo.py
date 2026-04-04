"""
utils/geo.py
Geospatial utility functions - Haversine distance and region lookup.
"""

import math

# City region grid - each region covers roughly 5km x 5km around Bangalore.
# region_id is the Kafka partition key so all events for a region
# land on the same partition and the same processor instance.
REGION_BOUNDS = {
    "BLR_NORTH":   {"lat_min": 13.00, "lat_max": 13.15, "lng_min": 77.50, "lng_max": 77.70},
    "BLR_SOUTH":   {"lat_min": 12.85, "lat_max": 13.00, "lng_min": 77.50, "lng_max": 77.70},
    "BLR_EAST":    {"lat_min": 12.90, "lat_max": 13.05, "lng_min": 77.70, "lng_max": 77.85},
    "BLR_WEST":    {"lat_min": 12.90, "lat_max": 13.05, "lng_min": 77.35, "lng_max": 77.50},
    "BLR_CENTRAL": {"lat_min": 12.95, "lat_max": 13.05, "lng_min": 77.55, "lng_max": 77.65},
}

DEFAULT_REGION = "BLR_SOUTH"


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Compute great-circle distance between two coordinates in kilometres.
    Uses the Haversine formula, accurate to within 0.5% for distances under 50km.
    """
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def get_region(lat: float, lng: float) -> str:
    """
    Return the region_id for a given coordinate.
    Falls back to DEFAULT_REGION if the coordinate is outside all defined regions.
    """
    for region_id, bounds in REGION_BOUNDS.items():
        if (bounds["lat_min"] <= lat <= bounds["lat_max"] and
                bounds["lng_min"] <= lng <= bounds["lng_max"]):
            return region_id
    return DEFAULT_REGION


def adjacent_regions(region_id: str) -> list:
    """
    Return adjacent region IDs for boundary-case matching.
    Used when no driver is found in the primary region.
    """
    adjacency = {
        "BLR_NORTH":   ["BLR_CENTRAL", "BLR_EAST", "BLR_WEST"],
        "BLR_SOUTH":   ["BLR_CENTRAL", "BLR_EAST", "BLR_WEST"],
        "BLR_EAST":    ["BLR_CENTRAL", "BLR_NORTH", "BLR_SOUTH"],
        "BLR_WEST":    ["BLR_CENTRAL", "BLR_NORTH", "BLR_SOUTH"],
        "BLR_CENTRAL": ["BLR_NORTH", "BLR_SOUTH", "BLR_EAST", "BLR_WEST"],
    }
    return adjacency.get(region_id, [])
