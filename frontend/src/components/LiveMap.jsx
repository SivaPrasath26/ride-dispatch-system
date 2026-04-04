// frontend/src/components/LiveMap.jsx
// Leaflet map showing live driver positions.
// Green marker = AVAILABLE, red = BUSY, grey = OFFLINE.
// Positions refresh every 2 seconds via polling.

import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const STATUS_COLOR = {
  AVAILABLE: "#16a34a",
  BUSY: "#dc2626",
  OFFLINE: "#9ca3af",
};

function DriverMarkers({ drivers }) {
  return drivers.map((d) => (
    <CircleMarker
      key={d.driver_id}
      center={[parseFloat(d.lat), parseFloat(d.lng)]}
      radius={7}
      pathOptions={{
        fillColor: STATUS_COLOR[d.status] || "#9ca3af",
        fillOpacity: 0.9,
        color: "#fff",
        weight: 1.5,
      }}
    >
      <Popup>
        <strong>{d.vehicle_type}</strong>
        <br />
        {d.driver_id.slice(0, 8)}...
        <br />
        Status: {d.status}
      </Popup>
    </CircleMarker>
  ));
}

export default function LiveMap({ drivers = [], center = [12.9716, 77.5946], zoom = 12, children }) {
  return (
    <MapContainer
      center={center}
      zoom={zoom}
      style={{ height: "100%", width: "100%", borderRadius: "8px" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <DriverMarkers drivers={drivers} />
      {children}
    </MapContainer>
  );
}
