/* 道の駅すごろく: goal-first, forward-only station route planner.
 * Geometry uses great-circle distance for lengths and local tangent plane
 * for progress/corridor; it is NOT a road-routing or travel-time engine.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.SugorokuRoute = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";
  const R = Math.PI / 180;
  const KM_PER_DEGREE = 111.195;
  const LABELS = ["北", "北東", "東", "南東", "南", "南西", "西", "北西"];
  const DIR_BEARINGS = {north: 0, northeast: 45, east: 90, southeast: 135,
    south: 180, southwest: 225, west: 270, northwest: 315};

  function km(a, b) {
    const la = Number(a.lat) * R, lb = Number(b.lat) * R;
    const dl = (Number(b.lng) - Number(a.lng)) * R;
    const h = Math.sin((lb - la) / 2) ** 2 +
      Math.cos(la) * Math.cos(lb) * Math.sin(dl / 2) ** 2;
    return 12742 * Math.atan2(Math.sqrt(Math.max(0, h)), Math.sqrt(Math.max(0, 1 - h)));
  }

  function relative(origin, point) {
    return {
      x: (Number(point.lng) - Number(origin.lng)) *
         Math.cos(((Number(origin.lat) + Number(point.lat)) / 2) * R) * KM_PER_DEGREE,
      y: (Number(point.lat) - Number(origin.lat)) * KM_PER_DEGREE
    };
  }

  function heading(origin, point) {
    const p = relative(origin, point);
    return (Math.atan2(p.x, p.y) / R + 360) % 360;
  }

  function difference(a, b) {
    return Math.abs(((a - b + 540) % 360) - 180);
  }

  function compass(degrees) {
    return LABELS[Math.round(degrees / 45) % LABELS.length];
  }

  function usable(point) {
    return point && Number.isFinite(Number(point.lat)) &&
      Number.isFinite(Number(point.lng)) &&
      Math.abs(Number(point.lat)) <= 90 && Math.abs(Number(point.lng)) <= 180;
  }

  function stopCandidates(origin, goal, stations, corridorKm) {
    const g = relative(origin, goal), denom = g.x * g.x + g.y * g.y;
    const direct = Math.sqrt(denom);
    if (!direct) return [];
    return stations.map(station => {
      const p = relative(origin, station);
      const along = (p.x * g.x + p.y * g.y) / direct;
      const sideways = Math.abs(p.x * g.y - p.y * g.x) / direct;
      return {station, along, sideways};
    }).filter(p => p.station !== goal &&
      p.station.id !== undefined && p.station.id !== goal.id &&
      p.along > Math.max(1, direct * 0.04) &&
      p.along < direct - Math.max(1, direct * 0.04) &&
      p.sideways <= corridorKm &&
      // Eliminate sharp turns at the origin/goal even within the corridor.
      p.sideways <= 2 + 0.85 * Math.min(p.along, direct - p.along)
    ).sort((a, b) => a.along - b.along);
  }

  function makeRoute(origin, goal, stations, totalStations, directKm, corridorKm) {
    const intermediateCount = totalStations - 1;
    if (!intermediateCount) {
      return {points: [goal], straightLegKm: km(origin, goal), count: 1};
    }
    const candidates = stopCandidates(origin, goal, stations, corridorKm);
    if (candidates.length < intermediateCount) return null;

    // Dynamic programming over monotonically increasing progress toward goal.
    // A route can't double back or zigzag across the origin in reverse.
    const layers = [];
    const maxRatio = 1.30;
    for (let step = 0; step < intermediateCount; step++) {
      const layer = Array(candidates.length).fill(null);
      for (let j = step; j < candidates.length; j++) {
        const target = candidates[j], targetProgress = target.along / directKm;
        const ideal = (step + 1) / totalStations;
        const spreadPenalty = Math.abs(targetProgress - ideal) * directKm * 0.25;
        if (!step) {
          const length = km(origin, target.station);
          if (length <= directKm * maxRatio) {
            layer[j] = {length, score: length + spreadPenalty, indices: [j]};
          }
          continue;
        }
        for (let i = step - 1; i < j; i++) {
          const before = layers[step - 1][i];
          if (!before || target.along - candidates[i].along < Math.max(1, directKm * 0.025)) continue;
          const length = before.length + km(candidates[i].station, target.station);
          if (length > directKm * maxRatio) continue;
          const score = before.score + km(candidates[i].station, target.station) + spreadPenalty;
          if (!layer[j] || score < layer[j].score) {
            layer[j] = {length, score, indices: [...before.indices, j]};
          }
        }
      }
      layers.push(layer);
    }

    let best = null;
    const last = layers[layers.length - 1];
    for (let i = 0; i < last.length; i++) {
      const state = last[i];
      if (!state) continue;
      const total = state.length + km(candidates[i].station, goal);
      if (total > directKm * maxRatio + 1e-6) continue;
      const result = {points: [...state.indices.map(j => candidates[j].station), goal],
                      straightLegKm: total, score: state.score + km(candidates[i].station, goal),
                      count: totalStations};
      if (!best || result.score < best.score) best = result;
    }
    return best;
  }

  function plan({origin, stations, distanceKm, toleranceKm = 10, count = 3,
                 direction = "all", random = Math.random}) {
    if (!usable(origin) || !Array.isArray(stations) || !Number.isFinite(distanceKm) ||
        distanceKm <= 0 || !Number.isFinite(toleranceKm) || toleranceKm < 0 ||
        !Number.isInteger(count) || count < 1 || count > 6 ||
        !(direction === "all" || Object.hasOwn(DIR_BEARINGS, direction))) {
      return {ok: false, reason: "invalid_input"};
    }
    const pool = stations.filter(s => usable(s) && s.id !== undefined &&
      s.id !== null && s.gacha !== false);
    const goals = pool.map(station => ({
      station, distance: km(origin, station), bearing: heading(origin, station)
    })).filter(g => g.distance >= Math.max(1, distanceKm - toleranceKm) &&
      g.distance <= distanceKm + toleranceKm &&
      (direction === "all" || difference(g.bearing, DIR_BEARINGS[direction]) <= 45));
    // Prefer destinations near the user-selected distance; keep gacha variety.
    goals.sort((a, b) => Math.abs(a.distance - distanceKm) -
                               Math.abs(b.distance - distanceKm));
    const options = [];
    for (const candidate of goals) {
      const corridorKm = Math.min(35, Math.max(6, candidate.distance * 0.20));
      const route = makeRoute(origin, candidate.station, pool, count,
                              candidate.distance, corridorKm);
      if (!route) continue;
      options.push({
        ...route, goal: candidate.station, goalDistanceKm: candidate.distance,
        bearingDegrees: candidate.bearing, directionName: compass(candidate.bearing),
        corridorKm,
        straightDetourRatio: route.straightLegKm / candidate.distance,
      });
    }
    if (!options.length) {
      return {ok: false, reason: goals.length ? "insufficient_forward_stations" : "no_goal",
              goalCandidates: goals.length};
    }
    options.sort((a, b) =>
      Math.abs(a.goalDistanceKm - distanceKm) - Math.abs(b.goalDistanceKm - distanceKm) ||
      a.straightDetourRatio - b.straightDetourRatio);
    // Random among the twelve closest workable destinations, not all distant ones.
    const shortlist = options.slice(0, 12);
    const picked = shortlist[Math.min(shortlist.length - 1,
      Math.max(0, Math.floor(random() * shortlist.length)))];
    return {ok: true, ...picked, goalCandidates: goals.length,
      viableGoals: options.length};
  }

  return {km, heading, compass, relative, stopCandidates, plan};
});
