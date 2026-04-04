// frontend/src/pages/RiderView.jsx
// Rider flow: enter pickup/dropoff, request ride, poll for driver assignment.

import { useState, useEffect, useRef } from "react";
import LiveMap from "../components/LiveMap";
import { createRide, pollMatch, cancelRide, getActiveDrivers } from "../services/api";

const BLR_CENTER = [12.9716, 77.5946];

export default function RiderView() {
  const [drivers, setDrivers] = useState([]);
  const [pickup, setPickup] = useState({ lat: 12.9716, lng: 77.5946 });
  const [dropoff, setDropoff] = useState({ lat: 13.0827, lng: 77.6065 });
  const [rideId, setRideId] = useState(null);
  const [status, setStatus] = useState(null);  // SEARCHING | MATCHED | TIMEOUT | CANCELLED
  const [driver, setDriver] = useState(null);
  const [loading, setLoading] = useState(false);
  const pollRef = useRef(null);

  // Refresh driver positions every 2 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const data = await getActiveDrivers();
        setDrivers(data);
      } catch (_) {}
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // Poll for match result
  useEffect(() => {
    if (!rideId || status === "MATCHED" || status === "TIMEOUT") return;

    pollRef.current = setInterval(async () => {
      try {
        const result = await pollMatch(rideId);
        setStatus(result.status);
        if (result.status === "MATCHED") {
          setDriver(result.driver);
          clearInterval(pollRef.current);
        }
        if (result.status === "TIMEOUT") {
          clearInterval(pollRef.current);
        }
      } catch (_) {}
    }, 2000);

    return () => clearInterval(pollRef.current);
  }, [rideId, status]);

  async function handleRequestRide() {
    setLoading(true);
    setDriver(null);
    setStatus(null);
    try {
      const result = await createRide(
        pickup.lat, pickup.lng,
        dropoff.lat, dropoff.lng,
        "rider-" + Date.now()
      );
      setRideId(result.ride_id);
      setStatus("SEARCHING");
    } catch (e) {
      alert("Failed to create ride. Is the API running?");
    } finally {
      setLoading(false);
    }
  }

  async function handleCancel() {
    if (!rideId) return;
    await cancelRide(rideId);
    setStatus("CANCELLED");
    clearInterval(pollRef.current);
  }

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "sans-serif" }}>
      {/* Sidebar */}
      <div style={{ width: 320, padding: 20, background: "#f9fafb", borderRight: "1px solid #e5e7eb", overflowY: "auto" }}>
        <h2 style={{ marginBottom: 16 }}>Request a Ride</h2>

        <label style={{ fontSize: 12, color: "#6b7280" }}>Pickup (lat, lng)</label>
        <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
          <input type="number" step="0.0001" value={pickup.lat}
            onChange={e => setPickup(p => ({ ...p, lat: parseFloat(e.target.value) }))}
            style={{ flex: 1, padding: "6px 8px", border: "1px solid #d1d5db", borderRadius: 4 }} />
          <input type="number" step="0.0001" value={pickup.lng}
            onChange={e => setPickup(p => ({ ...p, lng: parseFloat(e.target.value) }))}
            style={{ flex: 1, padding: "6px 8px", border: "1px solid #d1d5db", borderRadius: 4 }} />
        </div>

        <label style={{ fontSize: 12, color: "#6b7280" }}>Dropoff (lat, lng)</label>
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          <input type="number" step="0.0001" value={dropoff.lat}
            onChange={e => setDropoff(p => ({ ...p, lat: parseFloat(e.target.value) }))}
            style={{ flex: 1, padding: "6px 8px", border: "1px solid #d1d5db", borderRadius: 4 }} />
          <input type="number" step="0.0001" value={dropoff.lng}
            onChange={e => setDropoff(p => ({ ...p, lng: parseFloat(e.target.value) }))}
            style={{ flex: 1, padding: "6px 8px", border: "1px solid #d1d5db", borderRadius: 4 }} />
        </div>

        <button
          onClick={handleRequestRide}
          disabled={loading || status === "SEARCHING"}
          style={{
            width: "100%", padding: "10px", background: "#1d4ed8",
            color: "#fff", border: "none", borderRadius: 6, cursor: "pointer",
            marginBottom: 8, fontSize: 14, fontWeight: 600,
          }}
        >
          {loading ? "Requesting..." : "Request Ride"}
        </button>

        {status === "SEARCHING" && (
          <div>
            <p style={{ color: "#d97706", fontWeight: 600 }}>Searching for driver...</p>
            <button onClick={handleCancel}
              style={{ padding: "8px 12px", background: "#fee2e2", color: "#dc2626", border: "1px solid #fca5a5", borderRadius: 4, cursor: "pointer" }}>
              Cancel
            </button>
          </div>
        )}

        {status === "MATCHED" && driver && (
          <div style={{ background: "#f0fdf4", border: "1px solid #16a34a", borderRadius: 8, padding: 16 }}>
            <p style={{ color: "#15803d", fontWeight: 700, marginBottom: 8 }}>Driver Assigned!</p>
            <p><strong>Name:</strong> {driver.name}</p>
            <p><strong>Vehicle:</strong> {driver.vehicle_type} - {driver.vehicle_no}</p>
            <p><strong>Rating:</strong> {driver.rating}</p>
            <p><strong>Distance:</strong> {driver.distance_km} km</p>
            <p><strong>ETA:</strong> {Math.round(driver.eta_seconds / 60)} min</p>
          </div>
        )}

        {status === "TIMEOUT" && (
          <p style={{ color: "#dc2626" }}>No driver found nearby. Try again.</p>
        )}

        {status === "CANCELLED" && (
          <p style={{ color: "#6b7280" }}>Ride cancelled.</p>
        )}

        <div style={{ marginTop: 24, fontSize: 12, color: "#6b7280" }}>
          <p>{drivers.length} active drivers on map</p>
          <p>Green = Available, Red = Busy</p>
        </div>
      </div>

      {/* Map */}
      <div style={{ flex: 1 }}>
        <LiveMap drivers={drivers} center={BLR_CENTER} zoom={12} />
      </div>
    </div>
  );
}
