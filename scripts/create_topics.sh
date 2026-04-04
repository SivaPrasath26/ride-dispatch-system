#!/bin/bash
# scripts/create_topics.sh
# Run once after Kafka container is healthy to create all required topics.

set -e

KAFKA_CONTAINER="kafka"
BOOTSTRAP="localhost:9092"

echo "[Topics] Creating Kafka topics..."

docker exec $KAFKA_CONTAINER kafka-topics.sh \
  --bootstrap-server $BOOTSTRAP \
  --create --if-not-exists \
  --topic ride_requests \
  --partitions 12 \
  --replication-factor 1 \
  --config retention.ms=604800000

docker exec $KAFKA_CONTAINER kafka-topics.sh \
  --bootstrap-server $BOOTSTRAP \
  --create --if-not-exists \
  --topic driver_location \
  --partitions 24 \
  --replication-factor 1 \
  --config retention.ms=86400000

docker exec $KAFKA_CONTAINER kafka-topics.sh \
  --bootstrap-server $BOOTSTRAP \
  --create --if-not-exists \
  --topic ride_events \
  --partitions 12 \
  --replication-factor 1 \
  --config retention.ms=2592000000

echo "[Topics] All topics created. Listing:"
docker exec $KAFKA_CONTAINER kafka-topics.sh \
  --bootstrap-server $BOOTSTRAP \
  --list
