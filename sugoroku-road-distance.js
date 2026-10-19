/* Optional road-distance preview for 道の駅すごろく.
 * Uses a volunteer-operated demo endpoint ONLY when the user presses
 * the external-service button. Not a 125cc motorcycle routing engine.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.SugorokuRoadDistance = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";
  const ROUTER = "https://routing.openstreetmap.de/routed-car/route/v1/driving/";
  const cache = new Map();
  let lastRequestAt = 0;

  function validPoint(point) {
    return point && Number.isFinite(Number(point.lat)) &&
      Number.isFinite(Number(point.lng)) &&
      Number(point.lat) >= -90 && Number(point.lat) <= 90 &&
      Number(point.lng) >= -180 && Number(point.lng) <= 180;
  }

  function buildRequestUrl(origin, points) {
    if (!validPoint(origin) || !Array.isArray(points) ||
        !points.length || points.length > 6 || !points.every(validPoint)) {
      throw new Error("invalid_waypoints");
    }
    const coordinates = [origin, ...points].map(point =>
      Number(point.lng).toFixed(6) + "," + Number(point.lat).toFixed(6)).join(";");
    return ROUTER + coordinates + "?overview=false&steps=false&alternatives=false";
  }

  function decodeRoute(payload, legCount, minimumKm) {
    if (payload?.code !== "Ok" || !Array.isArray(payload.routes) ||
        payload.routes.length === 0) throw new Error("no_road_route");
    const route = payload.routes[0];
    if (!Number.isFinite(route.distance) || route.distance <= 0 ||
        !Array.isArray(route.legs) || route.legs.length !== legCount ||
        route.legs.some(leg => !Number.isFinite(leg.distance) || leg.distance < 0)) {
      throw new Error("invalid_road_distance");
    }
    const totalKm = route.distance / 1000;
    const segmentsKm = route.legs.map(leg => leg.distance / 1000);
    const sum = segmentsKm.reduce((a, b) => a + b, 0);
    if (Math.abs(sum - totalKm) > Math.max(0.2, totalKm * 0.01) ||
        totalKm + 0.5 < minimumKm) throw new Error("invalid_road_distance");
    return {totalKm, segmentsKm, provider: "OSRM / OpenStreetMap",
            profile: "car", indicative: true};
  }

  async function calculate({origin, points, minimumKm = 0,
                            fetchImpl = typeof fetch !== "undefined" ? fetch : null}) {
    const url = buildRequestUrl(origin, points);
    if (!fetchImpl) throw new Error("network_unavailable");
    if (!Number.isFinite(minimumKm) || minimumKm < 0) throw new Error("invalid_minimum");
    const stored = cache.get(url);
    if (stored) return {...stored, fromCache: true};
    // No automated / bulk requests to this volunteer demo server.
    const now = Date.now();
    if (now - lastRequestAt < 1250) throw new Error("request_interval");
    lastRequestAt = now;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 9000);
    let response;
    try {
      response = await fetchImpl(url, {
        method: "GET", cache: "no-store", signal: controller.signal,
        referrerPolicy: "strict-origin-when-cross-origin"
      });
      if (!response || !response.ok) throw new Error("routing_http_error");
      const payload = await response.json();
      const result = decodeRoute(payload, points.length, minimumKm);
      if (cache.size >= 25) cache.delete(cache.keys().next().value);
      cache.set(url, result);
      return {...result, fromCache: false};
    } finally {
      clearTimeout(timeout);
    }
  }

  return {buildRequestUrl, decodeRoute, calculate};
});
