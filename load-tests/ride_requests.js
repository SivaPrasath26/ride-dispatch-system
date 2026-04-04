// load-tests/ride_requests.js
// k6 load test - ramps to 1,000 req/sec and holds for 10 minutes.
// Install k6: brew install k6 (mac) or choco install k6 (windows)
// Run: k6 run load-tests/ride_requests.js

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "2m", target: 100 },   // ramp up
    { duration: "6m", target: 1000 },  // hold at target
    { duration: "2m", target: 0 },     // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(99)<200"],  // P99 under 200ms
    http_req_failed:   ["rate<0.01"], // error rate under 1%
  },
};

const BASE_URL = __ENV.API_URL || "http://localhost:5000/api/v1";
let TOKEN = "";

export function setup() {
  const resp = http.post(`${BASE_URL}/auth/token`,
    JSON.stringify({ user_id: "k6-test", role: "rider" }),
    { headers: { "Content-Type": "application/json" } }
  );
  return { token: resp.json("access_token") };
}

export default function (data) {
  const headers = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${data.token}`,
  };

  // Randomise pickup across Bangalore to spread across regions
  const lat = 12.85 + Math.random() * 0.30;
  const lng = 77.35 + Math.random() * 0.50;

  const res = http.post(`${BASE_URL}/ride`, JSON.stringify({
    rider_id: `k6-rider-${__VU}-${__ITER}`,
    pickup_lat: lat,
    pickup_lng: lng,
    dropoff_lat: lat + 0.05,
    dropoff_lng: lng + 0.05,
  }), { headers });

  check(res, {
    "status is 202": (r) => r.status === 202,
    "has ride_id":   (r) => r.json("ride_id") !== undefined,
  });

  sleep(0.001);
}
