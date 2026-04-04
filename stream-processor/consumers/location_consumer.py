"""
consumers/location_consumer.py
Kafka consumer for the driver_location topic.
Higher partition count (24 vs 12) to handle the larger volume -
10,000 drivers x 1 update every 5 seconds = 2,000 events/sec.
"""

import json
import logging
import os
from confluent_kafka import Consumer, KafkaError

log = logging.getLogger(__name__)

TOPIC = "driver_location"
GROUP_ID = os.getenv("CONSUMER_GROUP_LOCATION", "location-updater")


def build_consumer() -> Consumer:
    return Consumer({
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "group.id": GROUP_ID,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "max.poll.interval.ms": 300000,
        "session.timeout.ms": 30000,
        "heartbeat.interval.ms": 3000,
    })


def run_location_consumer(location_handler) -> None:
    """Blocking consumer loop for driver location events."""
    consumer = build_consumer()
    consumer.subscribe([TOPIC])
    log.info(f"[LocationConsumer] Subscribed to {TOPIC} (group={GROUP_ID})")

    try:
        while True:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                log.error(f"[LocationConsumer] Kafka error: {msg.error()}")
                continue

            try:
                event = json.loads(msg.value().decode("utf-8"))
                location_handler.handle(event)
                consumer.commit(message=msg, asynchronous=False)
            except Exception as e:
                log.exception(f"[LocationConsumer] Failed to process event: {e}")

    except KeyboardInterrupt:
        log.info("[LocationConsumer] Shutting down")
    finally:
        consumer.close()
