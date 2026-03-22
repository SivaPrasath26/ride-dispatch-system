# Ride Dispatch System

Real-time ride matching system. A rider requests a trip, the nearest available driver gets assigned under 200ms.

Built as my M.Sc. Data Science major project.

## Stack

- **Kafka** - event streaming for ride requests and driver location updates
- **Redis** - geospatial driver index, ride state, assignment results
- **Python** - stream processor and matching engine
- **FastAPI** - REST API
- **PostgreSQL** - ride history and driver profiles
- **React + Leaflet.js** - live map frontend
- **Prometheus + Grafana** - metrics and dashboards
- **Docker Compose** - runs everything locally

## How it works

Rider submits a pickup location. The stream processor queries Redis for nearby available drivers, picks the nearest one, and atomically assigns them using a Lua script to prevent double-booking. The API returns a `ride_id` immediately and the rider polls for the result.

Driver positions stream in from Kafka every 5 seconds and update the Redis geo index.

## Status

Work in progress. Building through March to May 2025.

## Running locally

```bash
git clone https://github.com/SivaPrasath26/ride-dispatch-system.git
cd ride-dispatch-system
docker compose up -d
```
