"""
state/postgres_store.py
Asynchronous PostgreSQL persistence layer.

PostgreSQL is NOT in the critical matching path. All matching decisions
are made using Redis. PostgreSQL stores the historical record of rides
for analytics, reporting, and audit purposes.

Writes happen in a background thread so they never block the matching engine.
"""

import os
import psycopg2
import psycopg2.pool
import threading
from datetime import datetime


class PostgresStore:
    def __init__(self):
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=os.getenv("POSTGRES_DSN", "postgresql://rideuser:ridepass@localhost:5432/ridedb")
        )
        self._lock = threading.Lock()

    def _get_conn(self):
        return self.pool.getconn()

    def _release_conn(self, conn):
        self.pool.putconn(conn)

    def save_ride(self, ride_id: str, rider_id: str, region_id: str,
                  pickup_lat: float, pickup_lng: float,
                  dropoff_lat: float = None, dropoff_lng: float = None) -> None:
        """
        Persist a new ride record. Called asynchronously from the stream processor
        so it does not block the matching response.
        """
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO rides
                        (ride_id, rider_id, status, region_id,
                         pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, requested_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ride_id) DO NOTHING
                """, (ride_id, rider_id, "SEARCHING", region_id,
                      pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, datetime.utcnow()))
            conn.commit()
        except Exception as e:
            print(f"[PostgresStore] save_ride error: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self._release_conn(conn)

    def update_ride_matched(self, ride_id: str, driver_id: str,
                             distance_km: float, latency_ms: int) -> None:
        """Update ride record when a driver is successfully assigned."""
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE rides
                    SET status = 'MATCHED',
                        driver_id = %s,
                        matched_at = %s,
                        distance_km = %s,
                        matching_latency_ms = %s
                    WHERE ride_id = %s
                """, (driver_id, datetime.utcnow(), distance_km, latency_ms, ride_id))
                # Also write an event to the audit log
                cur.execute("""
                    INSERT INTO ride_events (ride_id, event_type, payload)
                    VALUES (%s, 'MATCHED', %s::jsonb)
                """, (ride_id, f'{{"driver_id": "{driver_id}", "distance_km": {distance_km}}}'))
            conn.commit()
        except Exception as e:
            print(f"[PostgresStore] update_ride_matched error: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self._release_conn(conn)

    def update_ride_timeout(self, ride_id: str) -> None:
        """Mark a ride as timed out after no driver was found."""
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE rides SET status = 'TIMEOUT' WHERE ride_id = %s
                """, (ride_id,))
                cur.execute("""
                    INSERT INTO ride_events (ride_id, event_type)
                    VALUES (%s, 'TIMEOUT')
                """, (ride_id,))
            conn.commit()
        except Exception as e:
            print(f"[PostgresStore] update_ride_timeout error: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self._release_conn(conn)

    def get_ride_history(self, rider_id: str, limit: int = 20, offset: int = 0) -> list:
        """Fetch paginated ride history for a rider."""
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT ride_id, driver_id, status, pickup_lat, pickup_lng,
                           requested_at, matched_at, distance_km, fare_amount
                    FROM rides
                    WHERE rider_id = %s
                    ORDER BY requested_at DESC
                    LIMIT %s OFFSET %s
                """, (rider_id, limit, offset))
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as e:
            print(f"[PostgresStore] get_ride_history error: {e}")
            return []
        finally:
            if conn:
                self._release_conn(conn)

    def save_driver(self, driver_id: str, name: str, phone: str,
                    license_no: str, vehicle_type: str, vehicle_no: str) -> None:
        """Upsert a driver record (used by seed script and registration)."""
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO drivers (driver_id, name, phone, license_no, vehicle_type, vehicle_no)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (driver_id) DO UPDATE
                    SET name = EXCLUDED.name
                """, (driver_id, name, phone, license_no, vehicle_type, vehicle_no))
            conn.commit()
        except Exception as e:
            print(f"[PostgresStore] save_driver error: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self._release_conn(conn)
