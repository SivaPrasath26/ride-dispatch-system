// frontend/src/services/api.js
// All API calls go through this module.
// Token is stored in memory only (not localStorage).

import axios from "axios";

const BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

let token = null;

export const api = axios.create({ baseURL: BASE });

api.interceptors.request.use((config) => {
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export async function login(userId, role) {
  const resp = await api.post("/auth/token", { user_id: userId, role });
  token = resp.data.access_token;
  return token;
}

export async function createRide(pickupLat, pickupLng, dropoffLat, dropoffLng, riderId) {
  const resp = await api.post("/ride", {
    rider_id: riderId,
    pickup_lat: pickupLat,
    pickup_lng: pickupLng,
    dropoff_lat: dropoffLat,
    dropoff_lng: dropoffLng,
  });
  return resp.data;
}

export async function pollMatch(rideId) {
  const resp = await api.get(`/match/${rideId}`);
  return resp.data;
}

export async function cancelRide(rideId) {
  const resp = await api.post(`/ride/${rideId}/cancel`);
  return resp.data;
}

export async function updateDriverLocation(driverData) {
  const resp = await api.post("/driver/location", driverData);
  return resp.data;
}

export async function setDriverStatus(driverId, status) {
  const resp = await api.patch("/driver/status", { driver_id: driverId, status });
  return resp.data;
}

export async function getActiveDrivers() {
  const resp = await api.get("/admin/drivers/active");
  return resp.data.drivers;
}

export async function getMetrics() {
  const resp = await api.get("/metrics/summary");
  return resp.data;
}
