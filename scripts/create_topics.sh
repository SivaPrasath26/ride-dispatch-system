#!/usr/bin/env bash
# Run once after Kafka container is healthy to create all required topics.

set -euo pipefail

KAFKA_CONTAINER=${KAFKA_CONTAINER:-kafka}
BOOTSTRAP=${BOOTSTRAP:-kafka:9092}
KAFKA_TOPICS_BIN=/usr/bin/kafka-topics

echo "[Topics] Creating Kafka topics..."

docker compose exec "$KAFKA_CONTAINER" "$KAFKA_TOPICS_BIN" \
  --bootstrap-server "$BOOTSTRAP" \
  --create --if-not-exists \
  --topic ride_requests \
  --partitions 12 \
  --replication-factor 1 \
  --config retention.ms=604800000

docker compose exec "$KAFKA_CONTAINER" "$KAFKA_TOPICS_BIN" \
  --bootstrap-server "$BOOTSTRAP" \
  --create --if-not-exists \
  --topic driver_location \
  --partitions 24 \
  --replication-factor 1 \
  --config retention.ms=86400000

docker compose exec "$KAFKA_CONTAINER" "$KAFKA_TOPICS_BIN" \
  --bootstrap-server "$BOOTSTRAP" \
  --create --if-not-exists \
  --topic ride_events \
  --partitions 12 \
  --replication-factor 1 \
  --config retention.ms=2592000000

echo "[Topics] All topics created. Listing:"
docker compose exec "$KAFKA_CONTAINER" "$KAFKA_TOPICS_BIN" \
  --bootstrap-server "$BOOTSTRAP" \
  --list
