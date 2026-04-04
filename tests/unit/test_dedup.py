"""
tests/unit/test_dedup.py
Unit tests for the deduplication cache using fakeredis.
fakeredis runs a Redis-compatible server in memory - no real Redis needed.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../stream-processor"))

import fakeredis
import pytest
from utils.dedup import DeduplicationCache


@pytest.fixture
def dedup():
    client = fakeredis.FakeRedis(decode_responses=True)
    return DeduplicationCache(client)


def test_new_event_not_seen(dedup):
    assert dedup.is_seen("event-001") is False


def test_mark_then_seen(dedup):
    dedup.mark_seen("event-002")
    assert dedup.is_seen("event-002") is True


def test_different_events_independent(dedup):
    dedup.mark_seen("event-003")
    assert dedup.is_seen("event-004") is False


def test_idempotent_mark(dedup):
    dedup.mark_seen("event-005")
    dedup.mark_seen("event-005")
    assert dedup.is_seen("event-005") is True
