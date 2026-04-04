-- migrations/init.sql
-- Runs automatically when PostgreSQL container starts for the first time.

-- ─── Riders ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS riders (
    rider_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(100) NOT NULL,
    phone       VARCHAR(15)  UNIQUE NOT NULL,
    email       VARCHAR(100) UNIQUE,
    rating      DECIMAL(2,1) DEFAULT 5.0,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- ─── Drivers ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS drivers (
    driver_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(100) NOT NULL,
    phone        VARCHAR(15)  UNIQUE NOT NULL,
    license_no   VARCHAR(20)  UNIQUE NOT NULL,
    vehicle_type VARCHAR(20)  NOT NULL DEFAULT 'SEDAN',
    vehicle_no   VARCHAR(15)  UNIQUE NOT NULL,
    rating       DECIMAL(2,1) DEFAULT 5.0,
    is_active    BOOLEAN      DEFAULT TRUE,
    created_at   TIMESTAMPTZ  DEFAULT NOW()
);

-- ─── Rides ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rides (
    ride_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rider_id              UUID REFERENCES riders(rider_id),
    driver_id             UUID REFERENCES drivers(driver_id),
    status                VARCHAR(20)    NOT NULL DEFAULT 'SEARCHING',
    pickup_lat            DECIMAL(9,6)   NOT NULL,
    pickup_lng            DECIMAL(9,6)   NOT NULL,
    dropoff_lat           DECIMAL(9,6),
    dropoff_lng           DECIMAL(9,6),
    region_id             VARCHAR(30)    NOT NULL,
    requested_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    matched_at            TIMESTAMPTZ,
    completed_at          TIMESTAMPTZ,
    distance_km           DECIMAL(6,2),
    fare_amount           DECIMAL(8,2),
    matching_latency_ms   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_rides_status       ON rides(status);
CREATE INDEX IF NOT EXISTS idx_rides_region       ON rides(region_id, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_rides_requested_at ON rides(requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_rides_rider        ON rides(rider_id);
CREATE INDEX IF NOT EXISTS idx_rides_driver       ON rides(driver_id);

-- ─── Ride Events (audit log) ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ride_events (
    event_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ride_id     UUID REFERENCES rides(ride_id),
    event_type  VARCHAR(30)  NOT NULL,
    payload     JSONB,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ride_events_ride_id ON ride_events(ride_id);

-- ─── Seed a default test rider and driver for quick testing ───────────────────
INSERT INTO riders (rider_id, name, phone, email)
VALUES ('00000000-0000-0000-0000-000000000001', 'Test Rider', '9000000001', 'rider@test.com')
ON CONFLICT DO NOTHING;

INSERT INTO drivers (driver_id, name, phone, license_no, vehicle_type, vehicle_no)
VALUES ('00000000-0000-0000-0000-000000000002', 'Test Driver', '9000000002', 'KA-TEST-001', 'SEDAN', 'KA01AB0001')
ON CONFLICT DO NOTHING;
