"""
utils/metrics.py
Prometheus metrics definitions for the stream processor.
Exposed at :8001/metrics and scraped by Prometheus every 15s.
"""

from prometheus_client import Counter, Histogram, Gauge, start_http_server
import os

# ─── Counters ─────────────────────────────────────────────────────────────────

ride_requests_total = Counter(
    "ride_requests_total",
    "Total ride request events consumed from Kafka",
    ["region_id"]
)

rides_matched_total = Counter(
    "rides_matched_total",
    "Total rides successfully matched with a driver",
    ["region_id"]
)

rides_timeout_total = Counter(
    "rides_timeout_total",
    "Rides that timed out with no driver found",
    ["region_id"]
)

late_events_dropped_total = Counter(
    "late_events_dropped_total",
    "Location events discarded because they were older than the stored last_seen",
    ["region_id"]
)

duplicate_events_skipped_total = Counter(
    "duplicate_events_skipped_total",
    "Events skipped due to deduplication cache hit",
    ["topic"]
)

assignment_attempts_total = Counter(
    "assignment_attempts_total",
    "Lua script executions for atomic driver assignment",
    ["result"]  # success | failure (driver taken)
)

# ─── Histograms ───────────────────────────────────────────────────────────────

matching_latency_ms = Histogram(
    "matching_latency_ms",
    "End-to-end matching time from Kafka consume to Redis assignment write, in ms",
    ["region_id"],
    buckets=[10, 25, 50, 75, 100, 150, 200, 300, 500, 1000]
)

georadius_latency_ms = Histogram(
    "georadius_latency_ms",
    "Latency of Redis GEORADIUS calls in ms",
    buckets=[0.5, 1, 2, 5, 10, 20, 50]
)

# ─── Gauges ───────────────────────────────────────────────────────────────────

active_drivers_count = Gauge(
    "active_drivers_count",
    "Number of drivers currently with AVAILABLE status in Redis",
    ["region_id"]
)

kafka_consumer_lag = Gauge(
    "kafka_consumer_lag",
    "Number of messages the consumer is behind the latest offset",
    ["topic", "partition"]
)


def start_metrics_server():
    """Start the Prometheus HTTP server on the configured port."""
    port = int(os.getenv("PROMETHEUS_PORT", 8001))
    start_http_server(port)
    print(f"[Metrics] Prometheus metrics server started on :{port}")
