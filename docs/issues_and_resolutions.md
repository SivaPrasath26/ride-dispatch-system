# Ride Dispatch System - End to End Setup, Issues, and Fixes

## 0. What This Project Is

Real-time ride dispatch simulation:

* Kafka → event stream (drivers + ride requests)
* Stream processor → matches nearest driver
* Redis → geo index (live drivers)
* FastAPI → exposes APIs
* React → visualizes drivers and rides

No manual installation of Kafka/Postgres needed. Everything runs via Docker.

---

## 1. Prerequisites (Must Not Skip)

### Install

* Docker Desktop (Windows)
* Node.js (only if running frontend locally, optional)
* Python (only for local debugging, optional)

### Verify Docker

Run:

```bash
docker info
```

If this fails, Docker is not running.

---

## 2. Project Setup (From Scratch)

### Step 1: Open Correct Terminal

Use PowerShell (normal or admin):

```bash
cd C:\Users\shiva\Documents\ride-dispatch-system
```

### Step 2: Fix Docker Context

```bash
docker context use desktop-linux
```

### Step 3: Validate

```bash
docker info
```

Must succeed before continuing.

---

## 3. Start Full System

```bash
docker compose up -d
```

This starts:

* kafka
* redis
* api-server
* stream-processor
* event-generator
* frontend

---

## 4. Kafka Critical Fix (Most Common Failure)

### Problem

* No drivers appear
* Redis empty

### Root Cause

* Kafka topics missing or corrupted

### Fix Sequence (Strict Order)

#### Stop services

```bash
docker compose stop api-server stream-processor event-generator kafka
```

#### Remove Kafka container

```bash
docker compose rm -f kafka
```

#### Remove Kafka volume

```bash
docker volume rm ride-dispatch-system_kafka-data
```

If error: "volume is in use"
Run again:

```bash
docker compose rm -f kafka
```

Then retry remove volume.

#### Start Kafka fresh

```bash
docker compose up -d kafka
```

#### Create topics

```bash
docker compose exec kafka kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic ride_requests --partitions 12 --replication-factor 1

docker compose exec kafka kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic driver_location --partitions 24 --replication-factor 1

docker compose exec kafka kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic ride_events --partitions 12 --replication-factor 1
```

#### Start rest

```bash
docker compose up -d stream-processor event-generator api-server frontend
```

---

## 5. Verify System Is Working

### Check Redis drivers

```bash
docker compose exec redis redis-cli KEYS drivers:geo:*
```

Expected:

* drivers:geo:BLR_SOUTH
* drivers:geo:BLR_NORTH

### Check count

```bash
docker compose exec redis redis-cli ZCARD drivers:geo:BLR_SOUTH
```

Expected:

* value > 0

---

## 6. Access Applications

* Frontend: [http://localhost:3000](http://localhost:3000)
* API: [http://localhost:5000](http://localhost:5000)

---

## 7. Common Issues and Fixes

### 7.1 Docker npipe Error

Issue:

```
permission denied npipe
```

Fix:

* Restart Docker Desktop
* Re-run:

```bash
docker context use desktop-linux
```

---

### 7.2 Redis Empty

Cause:

* Kafka not producing

Fix:

* Redo Kafka reset section

---

### 7.3 Volume In Use Error

Cause:

* Container still attached

Fix:

```bash
docker compose rm -f kafka
docker volume rm ride-dispatch-system_kafka-data
```

---

### 7.4 Frontend Blank Screen

Cause:

* React crash due to undefined coordinates

Fix:

* Add null checks before rendering map polylines

---

### 7.5 Map Fully Black

Cause:

* Wrong tile layer

Fix:

* Use valid tile provider (OSM / CARTO)

---

### 7.6 State Reset on Tab Switch

Cause:

* State inside component

Fix:

* Move state to App-level

---

### 7.7 Drivers Disappear

Cause:

* Polling tied to component lifecycle

Fix:

* Move polling to global context

---

## 8. How Data Flows (Critical Understanding)

1. Event generator → pushes driver locations + ride requests to Kafka
2. Stream processor → consumes events
3. Redis → stores driver geo index
4. Matching → nearest driver assigned
5. API → exposes driver + ride state
6. Frontend → polls API and renders map

---

## 9. What Is Currently Working

* Drivers generated continuously
* Stored in Redis geo index
* Matching happens automatically
* Frontend displays drivers

---

## 10. What Is Missing

* No real routing (straight lines only)
* No driver cancel handling
* No persistent DB (Postgres unused)
* No real-time streaming (polling only)

---

## 11. Next Improvements

### Backend

* Add cancel event → trigger re-match
* Add ride states (SEARCHING, ASSIGNED)

### Frontend

* Add routing polyline (OSRM)
* Add ETA
* Add WebSocket

### Infra

* Add monitoring (Kafka lag, Redis size)

---

## Final Summary

System depends entirely on Kafka + Redis working correctly.

If drivers are not visible:

* Kafka is broken
* Or topics not created

If UI is blank:

* Frontend crash

If Redis has data:

* Backend is working

Everything else is frontend or UX issue.
