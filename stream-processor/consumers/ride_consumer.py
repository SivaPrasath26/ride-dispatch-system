"""
consumers/ride_consumer.py
Kafka consumer for the ride_requests topic.

Uses manual offset commit (enable.auto.commit: false) so the offset
is only advanced after the event has been fully processed and written
to Redis. If the processor crashes mid-processing, the event will be
re-delivered and handled idempotently by the dedup cache.
"""

import json
import logging
import os
from confluent_kafka import Consumer, KafkaError

log = logging.getLogger(__name__)

TOPIC = "ride_requests"
GROUP_ID = os.getenv("CONSUMER_GROUP_RIDE", "matching-engine")


def build_consumer() -> Consumer:
    return Consumer({
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "group.id": GROUP_ID,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,           # manual commit only
        "max.poll.interval.ms": 300000,
        "session.timeout.ms": 30000,
        "heartbeat.interval.ms": 3000,
    })


def run_ride_consumer(ride_handler) -> None:
    """
    Blocking consumer loop. Calls ride_handler.handle() for each message
    and commits the offset only on success.
    """
    consumer = build_consumer()
    consumer.subscribe([TOPIC])
    log.info(f"[RideConsumer] Subscribed to {TOPIC} (group={GROUP_ID})")

    try:
        while True:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                log.error(f"[RideConsumer] Kafka error: {msg.error()}")
                continue

            try:
                event = json.loads(msg.value().decode("utf-8"))
                ride_handler.handle(event)
                consumer.commit(message=msg, asynchronous=False)
            except Exception as e:
                log.exception(f"[RideConsumer] Failed to process event: {e}")
                # Do NOT commit - let the event be redelivered

    except KeyboardInterrupt:
        log.info("[RideConsumer] Shutting down")
    finally:
        consumer.close()
