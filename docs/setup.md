# Setup Guide

## Local Development

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+ (for running tests outside Docker)
- Node.js 18+ (for frontend development)
- k6 (for load testing)

---

## Step 1: Clone and Configure

```bash
git clone https://github.com/SivaPrasath26/ride-dispatch-system.git
cd ride-dispatch-system

cp .env.example .env
```

Edit `.env` and set your values:

```env
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
REDIS_HOST=redis
REDIS_PORT=6379
POSTGRES_DSN=postgresql://rideuser:ridepass@postgres:5432/ridedb
MATCHING_RADIUS_KM=5
DRIVER_TTL_SECONDS=120
MATCH_TIMEOUT_SECONDS=30
JWT_SECRET=change-this-in-production
MAX_MATCHING_CANDIDATES=20
```

---

## Step 2: Start All Services

```bash
docker compose up -d
```

Wait about 30 seconds for all services to initialise, then verify:

```bash
docker compose ps
```

All services should show `healthy` or `running`.

---

## Step 3: Create Kafka Topics

```bash
./scripts/create_topics.sh
```

This creates:
- `ride_requests` — 12 partitions, 7-day retention
- `driver_location` — 24 partitions, 1-day retention
- `ride_events` — 12 partitions, 30-day retention

Verify:
```bash
docker compose exec kafka kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --list
```

---

## Step 4: Run Database Migrations

```bash
docker compose exec api-server alembic upgrade head
```

Verify tables:
```bash
docker compose exec postgres psql -U rideuser -d ridedb -c "\dt"
```

---

## Step 5: Seed Initial Drivers

```bash
docker compose exec api-server python scripts/seed_drivers.py
```

This creates 500 simulated drivers distributed across city regions with randomised starting positions.

---

## Step 6: Start Event Generator

The event generator runs as a Docker service automatically. To check it is producing events:

```bash
docker compose logs -f event-generator
```

You should see log lines like:
```
[Generator] Published ride_request: ride_abc123 region=BLR_SOUTH
[Generator] Published location_update: driver_456 lat=12.94 lng=77.61
```

---

## Step 7: Access the Services

| Service | URL | Credentials |
|---|---|---|
| Frontend | http://localhost:3000 | - |
| API Swagger | http://localhost:5000/docs | JWT token |
| Grafana | http://localhost:3001 | admin / admin |
| Prometheus | http://localhost:9090 | - |
| Redis Insight | http://localhost:8001 | - |

---

## Verify the System End-to-End

```bash
# 1. Create a ride request
curl -X POST http://localhost:5000/api/v1/ride \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{"pickup_lat":12.9716,"pickup_lng":77.5946,"dropoff_lat":13.0827,"dropoff_lng":77.6065}'

# Response: {"ride_id": "abc-123", "status": "SEARCHING"}

# 2. Poll for match (after 1-2 seconds)
curl http://localhost:5000/api/v1/match/abc-123 \
  -H "Authorization: Bearer <your_token>"

# Response: {"status": "MATCHED", "driver": {...}}
```

---

## Redis Verification

Check the geo index is populated:
```bash
docker compose exec redis redis-cli \
  GEORADIUS drivers:geo:BLR_SOUTH 77.5946 12.9716 5 km ASC COUNT 5
```

Check a driver hash:
```bash
docker compose exec redis redis-cli \
  HGETALL driver:<driver_id>
```

---

## Running Tests

```bash
# Unit tests
docker compose exec stream-processor pytest tests/unit/ -v

# Integration tests
docker compose exec stream-processor pytest tests/integration/ -v

# Race condition stress test
docker compose exec stream-processor \
  pytest tests/integration/test_race_condition.py -v -s

# Coverage
docker compose exec stream-processor \
  pytest --cov=. --cov-report=term-missing
```

---

## Load Testing

```bash
# Install k6
brew install k6          # macOS
# or
sudo apt install k6      # Ubuntu

# Run load test
k6 run load-tests/ride_requests.js

# Expected results:
# ✓ http_req_duration p(99) < 200ms
# ✓ http_req_failed   rate  < 1%
```

---

## Stopping Services

```bash
# Stop all containers
docker compose down

# Stop and remove volumes (full reset)
docker compose down -v
```

---

## AWS EC2 Deployment

```bash
# On your EC2 instance (t3.medium recommended)
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git

git clone https://github.com/SivaPrasath26/ride-dispatch-system.git
cd ride-dispatch-system
cp .env.example .env
# Edit .env with production values

docker compose up -d
./scripts/create_topics.sh
docker compose exec api-server alembic upgrade head
```

Make sure ports 80, 3000, 5000 are open in your EC2 security group.

---

## Troubleshooting

**Kafka not starting:**
```bash
docker compose logs kafka
# Check CLUSTER_ID is set correctly in docker-compose.yml
```

**Stream processor not consuming:**
```bash
docker compose logs stream-processor
# Check KAFKA_BOOTSTRAP_SERVERS matches kafka service name
```

**GEORADIUS returning empty:**
```bash
# Check drivers are being seeded
docker compose exec redis redis-cli ZCARD drivers:geo:BLR_SOUTH
# Should return > 0 after event generator runs for 30 seconds
```

**P99 latency above 200ms:**
```bash
# Check Redis connection pool size in stream-processor config
# Check Kafka consumer lag — if high, processor is backlogged
docker compose exec kafka kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group matching-engine
```
