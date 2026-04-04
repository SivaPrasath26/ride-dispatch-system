# Architecture

## System Overview

Event-driven architecture with a streaming backbone, an in-memory geospatial state store for low-latency matching, a relational database for persistence, and a Flask REST API for serving.

The write path (event ingestion and state updates) is fully decoupled from the read path (assignment serving). Redis is the source of truth for all live operational state. PostgreSQL only stores historical records and is never in the critical matching path.

---

## High Level Architecture

```mermaid
flowchart TD
    RA[Rider App] -->|POST /ride| GW[Flask API Gateway]
    DA[Driver App] -->|POST /location| GW

    GW -->|publish| KR[Kafka\nride_requests\n12 partitions]
    GW -->|publish| KL[Kafka\ndriver_location\n24 partitions]

    KR -->|consume| SP[Stream Processor\nPython]
    KL -->|consume| SP

    SP -->|GEOADD HSET EXPIRE| RD[(Redis\nGeo Index\nDriver State\nAssignments)]
    SP -.->|async write| PG[(PostgreSQL\nRide History\nAudit Log)]

    RD -->|HGETALL sub 5ms| GW
    GW -->|MATCHED response| RA

    EG[Event Generator\nSynthetic Data] -->|produce| KR
    EG -->|produce| KL

    PR[Prometheus] -->|scrape /metrics| SP
    PR -->|scrape /metrics| GW
    GF[Grafana] --> PR

    style SP fill:#d1fae5,stroke:#16a34a
    style RD fill:#ffe4e6,stroke:#f43f5e
    style PG fill:#dbeafe,stroke:#3b82f6
    style KR fill:#fef9c3,stroke:#ca8a04
    style KL fill:#fef9c3,stroke:#ca8a04
    style GW fill:#ede9fe,stroke:#8b5cf6
```

---

## Write Path - Ride Request

```mermaid
sequenceDiagram
    participant R as Rider App
    participant API as Flask API
    participant K as Kafka
    participant SP as Stream Processor
    participant RD as Redis
    participant PG as PostgreSQL

    R->>API: POST /ride {pickup_lat, pickup_lng}
    API->>API: assign ride_id, get region_id
    API->>K: publish ride_requests (key=region_id)
    API-->>R: 202 Accepted {ride_id, status: SEARCHING}

    K->>SP: consume event
    SP->>SP: check dedup SET (event_id)
    SP->>RD: GEORADIUS drivers:geo:{region} 5km ASC
    RD-->>SP: [driver_1, driver_2, driver_3]
    SP->>RD: HGET driver:{id} status
    RD-->>SP: AVAILABLE
    SP->>RD: Lua atomic assign (CAS)
    RD-->>SP: 1 (success)
    SP->>RD: HSET assignment:{ride_id} ...
    SP->>SP: SADD processed_events event_id
    SP-)PG: async INSERT rides (background thread)
```

---

## Read Path - Assignment Polling

```mermaid
sequenceDiagram
    participant R as Rider App
    participant API as Flask API
    participant RD as Redis

    loop every 2 seconds
        R->>API: GET /match/{ride_id}
        API->>RD: HGETALL assignment:{ride_id}
        alt assignment exists
            RD-->>API: {driver_id, name, eta...}
            API-->>R: 200 {status: MATCHED, driver: {...}}
        else not yet
            RD-->>API: nil
            API->>RD: HGET ride:{ride_id} status
            RD-->>API: SEARCHING
            API-->>R: 200 {status: SEARCHING}
        end
    end
```

---

## Write Path - Driver Location Update

```mermaid
sequenceDiagram
    participant D as Driver App
    participant API as Flask API
    participant K as Kafka
    participant SP as Stream Processor
    participant RD as Redis

    D->>API: POST /driver/location {lat, lng, status}
    API->>K: publish driver_location (key=region_id)
    API-->>D: 200 {acknowledged: true}

    K->>SP: consume event
    SP->>RD: HGET driver:{id} last_seen
    RD-->>SP: stored_timestamp

    alt event is fresh (ts >= stored_ts)
        SP->>RD: pipeline GEOADD + HSET + EXPIRE
        RD-->>SP: OK
    else event is stale (ts < stored_ts)
        SP->>SP: discard, increment late_events_dropped counter
    end
```

---

## Atomic Assignment - Race Condition Prevention

Two processors receiving requests near the same driver simultaneously:

```mermaid
sequenceDiagram
    participant P1 as Processor 1
    participant RD as Redis
    participant P2 as Processor 2

    P1->>RD: GEORADIUS - gets [D1, D2, D3]
    P2->>RD: GEORADIUS - gets [D1, D2, D3]

    P1->>RD: Lua script on D1
    Note over RD: HGET status = AVAILABLE
    Note over RD: HSET status = BUSY
    RD-->>P1: return 1 (success)
    Note over P1: D1 assigned to Ride-A

    P2->>RD: Lua script on D1
    Note over RD: HGET status = BUSY
    RD-->>P2: return 0 (fail)
    Note over P2: try D2 instead
    P2->>RD: Lua script on D2
    RD-->>P2: return 1 (success)
    Note over P2: D2 assigned to Ride-B
```

Lua script runs atomically - no other Redis client can interleave. Zero double-assignment guaranteed.

---

## Driver State Machine

```mermaid
stateDiagram-v2
    [*] --> AVAILABLE : driver comes online
    AVAILABLE --> BUSY : ride assigned (Lua CAS)
    BUSY --> AVAILABLE : ride completed
    AVAILABLE --> OFFLINE : driver goes offline
    OFFLINE --> AVAILABLE : driver comes back online
    AVAILABLE --> [*] : TTL expires after 120s no update
    BUSY --> [*] : TTL expires after 120s no update
```

---

## Ride Lifecycle

```mermaid
stateDiagram-v2
    [*] --> SEARCHING : POST /ride
    SEARCHING --> MATCHED : driver assigned
    SEARCHING --> TIMEOUT : 30s with no driver
    SEARCHING --> CANCELLED : rider cancels
    MATCHED --> IN_PROGRESS : driver starts trip
    IN_PROGRESS --> COMPLETED : trip ends
    IN_PROGRESS --> CANCELLED : cancellation
    TIMEOUT --> [*]
    CANCELLED --> [*]
    COMPLETED --> [*]
```

---

## Retry Strategy - No Driver Found

```mermaid
flowchart TD
    A[Ride Request Received] --> B{GEORADIUS 5km}
    B -->|drivers found| C{Any AVAILABLE?}
    B -->|none| D[wait 5s - retry 7km]
    C -->|yes| E[Lua atomic assign]
    C -->|none available| D
    E -->|success| F[MATCHED]
    E -->|all taken| D
    D --> G{GEORADIUS 7km}
    G -->|found| C
    G -->|none| H[wait 5s - retry 10km]
    H --> I{GEORADIUS 10km}
    I -->|found| C
    I -->|none| J[wait 5s - retry 15km]
    J --> K{GEORADIUS 15km}
    K -->|found| C
    K -->|none| L[TIMEOUT after 30s total]

    style F fill:#d1fae5,stroke:#16a34a
    style L fill:#fee2e2,stroke:#ef4444
```

---

## Kafka Design

```mermaid
flowchart LR
    subgraph Topics
        direction TB
        T1[ride_requests\n12 partitions\nkey = region_id\n7 day retention]
        T2[driver_location\n24 partitions\nkey = region_id\n1 day retention]
        T3[ride_events\n12 partitions\nkey = ride_id\n30 day retention]
    end

    subgraph Consumers
        CG1[matching-engine\nconsumer group]
        CG2[location-updater\nconsumer group]
        CG3[event-logger\nconsumer group]
    end

    T1 --> CG1
    T2 --> CG2
    T3 --> CG3
```

Partitioning by `region_id` means all events for the same city region land on the same partition. One processor instance owns all matching state for its region with no cross-partition coordination needed.

---

## Redis Data Structures

```mermaid
erDiagram
    GEO_INDEX {
        string key "drivers:geo:{region_id}"
        float score "geohash(lat, lng)"
        string member "driver_id"
    }
    DRIVER_HASH {
        string key "driver:{driver_id}"
        float lat
        float lng
        string status "AVAILABLE | BUSY | OFFLINE"
        float heading
        float speed_kmh
        int last_seen "unix timestamp"
        string region_id
        string driver_name
        string vehicle_type
        string vehicle_no
        float rating
        int ttl "120 seconds"
    }
    ASSIGNMENT_HASH {
        string key "assignment:{ride_id}"
        string driver_id
        string driver_name
        string vehicle_type
        string vehicle_no
        float rating
        float distance_km
        int eta_seconds
        int assigned_at
        int ttl "300 seconds"
    }
    DEDUP_SET {
        string key "processed_events"
        string members "event_id values"
        int ttl "86400 seconds"
    }
```

---

## PostgreSQL Schema

```mermaid
erDiagram
    riders {
        uuid rider_id PK
        varchar name
        varchar phone
        varchar email
        decimal rating
        timestamptz created_at
    }
    drivers {
        uuid driver_id PK
        varchar name
        varchar phone
        varchar license_no
        varchar vehicle_type
        varchar vehicle_no
        decimal rating
        boolean is_active
        timestamptz created_at
    }
    rides {
        uuid ride_id PK
        uuid rider_id FK
        uuid driver_id FK
        varchar status
        decimal pickup_lat
        decimal pickup_lng
        decimal dropoff_lat
        decimal dropoff_lng
        varchar region_id
        timestamptz requested_at
        timestamptz matched_at
        decimal distance_km
        integer matching_latency_ms
    }
    ride_events {
        uuid event_id PK
        uuid ride_id FK
        varchar event_type
        jsonb payload
        timestamptz created_at
    }

    riders ||--o{ rides : "requests"
    drivers ||--o{ rides : "serves"
    rides ||--o{ ride_events : "has"
```

---

## Key Design Decisions

| Decision | Choice | Why |
|---|---|---|
| State store | Redis geospatial sorted sets | Sub-ms GEORADIUS vs 5-20ms PostGIS |
| Kafka partition key | `region_id` | All same-region events on one partition, no cross-partition joins |
| Atomic assignment | Redis Lua script | All operations atomic, no external lock manager needed |
| Offset commit | Manual after Redis write | Safe crash recovery, no lost events |
| Deduplication | Redis SET with 24h TTL | O(1) lookup, prevents double-processing on re-delivery |
| Late events | Timestamp comparison | Prevents stale location overwriting latest position |
| PostgreSQL writes | Async background thread | Removes DB from critical path, Redis is source of truth |
