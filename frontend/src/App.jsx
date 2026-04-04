// frontend/src/App.jsx
// Main app with simple tab navigation between Rider, Driver, and Admin views.
// No react-router needed for this project - just state-based tab switching.

import { useState, useEffect } from "react";
import RiderView from "./pages/RiderView";
import DriverView from "./pages/DriverView";
import AdminDashboard from "./pages/AdminDashboard";
import { login } from "./services/api";

const TABS = ["Rider", "Driver", "Admin"];

export default function App() {
  const [activeTab, setActiveTab] = useState("Rider");
  const [ready, setReady] = useState(false);

  // Get a dev token on mount so all API calls work
  useEffect(() => {
    login("dev-user", "rider").then(() => setReady(true)).catch(() => setReady(true));
  }, []);

  if (!ready) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", fontFamily: "sans-serif" }}>
        Connecting to API...
      </div>
    );
  }

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", fontFamily: "sans-serif" }}>
      {/* Nav */}
      <div style={{
        display: "flex", alignItems: "center", gap: 4,
        padding: "0 20px", background: "#1e3a5f", height: 48,
      }}>
        <span style={{ color: "#93c5fd", fontWeight: 700, fontSize: 15, marginRight: 24 }}>
          Ride Dispatch
        </span>
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: "6px 16px", borderRadius: 4, border: "none", cursor: "pointer",
              background: activeTab === tab ? "#3b82f6" : "transparent",
              color: activeTab === tab ? "#fff" : "#93c5fd",
              fontWeight: activeTab === tab ? 600 : 400,
              fontSize: 13,
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* View */}
      <div style={{ flex: 1, overflow: "hidden" }}>
        {activeTab === "Rider" && <RiderView />}
        {activeTab === "Driver" && <DriverView />}
        {activeTab === "Admin" && <AdminDashboard />}
      </div>
    </div>
  );
}
