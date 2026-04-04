// frontend/src/pages/AdminDashboard.jsx
// System metrics dashboard - live driver map + stats bar + latency chart.

import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import LiveMap from "../components/LiveMap";
import { getActiveDrivers, getMetrics } from "../services/api";

export default function AdminDashboard() {
  const [drivers, setDrivers] = useState([]);
  const [metrics, setMetrics] = useState({});
  const [latencyHistory, setLatencyHistory] = useState([]);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const d = await getActiveDrivers();
        setDrivers(d);

        const m = await getMetrics();
        setMetrics(m);

        setLatencyHistory(prev => {
          const next = [...prev, {
            time: new Date().toLocaleTimeString(),
            active: m.active_drivers || 0,
          }].slice(-20); // keep last 20 points
          return next;
        });
      } catch (_) {}
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const available = drivers.filter(d => d.status === "AVAILABLE").length;
  const busy = drivers.filter(d => d.status === "BUSY").length;

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", fontFamily: "sans-serif" }}>
      {/* Stats bar */}
      <div style={{
        display: "flex", gap: 16, padding: "12px 20px",
        background: "#f9fafb", borderBottom: "1px solid #e5e7eb",
      }}>
        {[
          { label: "Active drivers", value: drivers.length },
          { label: "Available", value: available },
          { label: "Busy", value: busy },
          { label: "Note", value: "See Grafana :3001 for full metrics" },
        ].map(item => (
          <div key={item.label} style={{
            background: "#fff", border: "1px solid #e5e7eb",
            borderRadius: 8, padding: "10px 16px", minWidth: 120,
          }}>
            <p style={{ fontSize: 11, color: "#6b7280", margin: 0 }}>{item.label}</p>
            <p style={{ fontSize: 20, fontWeight: 700, margin: 0, color: "#111827" }}>{item.value}</p>
          </div>
        ))}
      </div>

      {/* Map + Chart */}
      <div style={{ flex: 1, display: "flex" }}>
        <div style={{ flex: 2 }}>
          <LiveMap drivers={drivers} center={[12.9716, 77.5946]} zoom={12} />
        </div>

        <div style={{ width: 320, padding: 16, borderLeft: "1px solid #e5e7eb" }}>
          <h3 style={{ fontSize: 13, color: "#374151", marginBottom: 12 }}>Active Drivers Over Time</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={latencyHistory}>
              <XAxis dataKey="time" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Line type="monotone" dataKey="active" stroke="#3b82f6" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>

          <div style={{ marginTop: 20, fontSize: 12, color: "#6b7280" }}>
            <p>For full observability:</p>
            <p>Prometheus: <a href="http://localhost:9090">:9090</a></p>
            <p>Grafana: <a href="http://localhost:3001">:3001</a></p>
          </div>
        </div>
      </div>
    </div>
  );
}
