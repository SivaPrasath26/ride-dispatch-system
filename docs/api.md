# API Reference

Base URL: `http://localhost:8000/api/v1`

Authentication: `Authorization: Bearer <jwt_token>` on all endpoints except `/health`.

---

## Rider Endpoints

### POST /ride
Create a new ride request. Returns immediately with a `ride_id` — matching happens asynchronously.

**Request**
```json
{
  "pickup_lat": 12.9716,
  "pickup_lng": 77.5946,
  "dropoff_lat": 13.0827,
  "dropoff_lng": 77.6065
}
```

**Response 202 Accepted**
```json
{
  "ride_id": "abc-123-uuid",
  "status": "SEARCHING",
  "region_id": "BLR_SOUTH"
}
```

---

### GET /match/{ride_id}
Poll for assignment result. Call every 2 seconds after creating a ride.

**Response — MATCHED**
```json
{
  "ride_id": "abc-123",
  "status": "MATCHED",
  "driver": {
    "driver_id": "driver_123",
    "name": "Ravi Kumar",
    "vehicle_type": "SEDAN",
    "vehicle_no": "KA01AB1234",
    "rating": 4.8,
    "distance_km": 1.34,
    "eta_seconds": 240
  }
}
```

**Response — still searching**
```json
{ "ride_id": "abc-123", "status": "SEARCHING" }
```

**Response — timed out**
```json
{ "ride_id": "abc-123", "status": "TIMEOUT" }
```

---

### POST /ride/{ride_id}/cancel
Cancel a ride in SEARCHING or MATCHED state.

**Response 200**
```json
{ "ride_id": "abc-123", "status": "CANCELLED" }
```

---

### GET /ride/{ride_id}
Get full ride details including timeline.

---

### GET /rides/history
Paginated list of rider's past rides (from PostgreSQL).

**Query params:** `page=1&per_page=20`

---

## Driver Endpoints

### POST /driver/location
Publish a driver location update. Called every 5 seconds by driver app.

**Request**
```json
{
  "lat": 12.9352,
  "lng": 77.6245,
  "heading": 270.0,
  "speed_kmh": 32.5,
  "status": "AVAILABLE"
}
```

**Response 200**
```json
{ "acknowledged": true }
```

---

### PATCH /driver/status
Toggle driver availability.

**Request**
```json
{ "status": "AVAILABLE" }
```

Valid values: `AVAILABLE`, `BUSY`, `OFFLINE`

---

### GET /driver/{driver_id}
Get driver profile (from PostgreSQL).

---

### GET /driver/{driver_id}/rides
Paginated ride history for a driver.

---

## Admin Endpoints

### GET /admin/drivers/active
Returns up to 200 active driver positions from Redis geo index. Used by frontend map polling.

**Response**
```json
{
  "drivers": [
    {
      "driver_id": "driver_123",
      "lat": 12.9352,
      "lng": 77.6245,
      "status": "AVAILABLE",
      "heading": 270.0
    }
  ],
  "count": 142
}
```

---

### GET /admin/regions
Driver density breakdown per region.

---

### GET /health
System health check — no auth required.

**Response**
```json
{
  "status": "healthy",
  "kafka": "connected",
  "redis": "connected",
  "postgres": "connected",
  "consumer_lag_ride_requests": 142,
  "consumer_lag_driver_location": 89,
  "active_drivers": 8432
}
```

---

### GET /metrics/summary
Aggregated system metrics for frontend dashboard.

**Response**
```json
{
  "rides_last_minute": 234,
  "active_drivers": 8432,
  "avg_matching_latency_ms": 47,
  "p99_matching_latency_ms": 183,
  "consumer_lag": 142,
  "timeout_rate_pct": 0.8
}
```

---

## Error Format

All errors follow this structure:

```json
{
  "error": "RIDE_NOT_FOUND",
  "message": "No ride found with id abc-123",
  "status_code": 404
}
```

| Error Code | HTTP | Trigger |
|---|---|---|
| `RIDE_NOT_FOUND` | 404 | ride_id does not exist |
| `DRIVER_NOT_AVAILABLE` | 409 | Driver is not AVAILABLE |
| `RATE_LIMIT_EXCEEDED` | 429 | More than 10 requests/min |
| `INVALID_COORDINATES` | 422 | lat/lng out of valid range |
| `UNAUTHORIZED` | 401 | Missing or invalid JWT |
| `REGION_NOT_FOUND` | 422 | Coordinates outside known regions |