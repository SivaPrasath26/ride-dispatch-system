"""
utils/geo.py  (api-server copy)
Region lookup shared by ride and driver routes.
"""

REGION_BOUNDS = {
    "BLR_NORTH":   {"lat_min": 13.00, "lat_max": 13.15, "lng_min": 77.50, "lng_max": 77.70},
    "BLR_SOUTH":   {"lat_min": 12.85, "lat_max": 13.00, "lng_min": 77.50, "lng_max": 77.70},
    "BLR_EAST":    {"lat_min": 12.90, "lat_max": 13.05, "lng_min": 77.70, "lng_max": 77.85},
    "BLR_WEST":    {"lat_min": 12.90, "lat_max": 13.05, "lng_min": 77.35, "lng_max": 77.50},
    "BLR_CENTRAL": {"lat_min": 12.95, "lat_max": 13.05, "lng_min": 77.55, "lng_max": 77.65},
}


def get_region(lat: float, lng: float) -> str:
    for region_id, bounds in REGION_BOUNDS.items():
        if (bounds["lat_min"] <= lat <= bounds["lat_max"] and
                bounds["lng_min"] <= lng <= bounds["lng_max"]):
            return region_id
    return "BLR_SOUTH"
