// frontend/src/pages/DriverView.jsx
// Driver view: shows current status toggle and current ride assignment.

import { useState, useEffect } from "react";
import LiveMap from "../components/LiveMap";
import { setDriverStatus } from "../services/api";

const DRIVER_ID = "driver-sim-001";
const BLR_CENTER = [12.9716, 77.5946];

export default function DriverView() {
  const [status, setStatus] = useState("AVAILABLE");
  const [position, setPosition] = useState({ lat: 12.9716, lng: 77.5946 });

  async function toggleStatus() {
    const next = status === "AVAILABLE" ? "OFFLINE" : "AVAILABLE";
    try {
      await setDriverStatus(DRIVER_ID, next);
      setStatus(next);
    } catch (e) {
      alert("Could not update status. Is the API running?");
    }
  }

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "sans-serif" }}>
      <div style={{ width: 280, padding: 20, background: "#f9fafb", borderRight: "1px solid #e5e7eb" }}>
        <h2 style={{ marginBottom: 16 }}>Driver Panel</h2>

        <div style={{
          padding: 16, borderRadius: 8, marginBottom: 16,
          background: status === "AVAILABLE" ? "#f0fdf4" : "#f9fafb",
          border: `1px solid ${status === "AVAILABLE" ? "#16a34a" : "#e5e7eb"}`,
        }}>
          <p style={{ fontWeight: 700, color: status === "AVAILABLE" ? "#15803d" : "#6b7280" }}>
            {status}
          </p>
          <p style={{ fontSize: 12, color: "#6b7280" }}>Driver ID: {DRIVER_ID.slice(0, 12)}...</p>
        </div>

        <button
          onClick={toggleStatus}
          style={{
            width: "100%", padding: 10,
            background: status === "AVAILABLE" ? "#fee2e2" : "#f0fdf4",
            color: status === "AVAILABLE" ? "#dc2626" : "#15803d",
            border: `1px solid ${status === "AVAILABLE" ? "#fca5a5" : "#86efac"}`,
            borderRadius: 6, cursor: "pointer", fontWeight: 600,
          }}
        >
          Go {status === "AVAILABLE" ? "Offline" : "Online"}
        </button>

        <div style={{ marginTop: 24, fontSize: 12, color: "#6b7280" }}>
          <p>Location updates are simulated by the event generator running in Docker.</p>
        </div>
      </div>

      <div style={{ flex: 1 }}>
        <LiveMap drivers={[]} center={BLR_CENTER} zoom={13} />
      </div>
    </div>
  );
}
