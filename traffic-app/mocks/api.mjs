import { randomUUID } from "node:crypto";
import { URL } from "node:url";
import {
  buildStats,
  filterIncidents,
  seedIncidents,
} from "./data.mjs";

const COOKIE_NAME = "traffic_app_uuid";

function createState() {
  return {
    incidents: seedIncidents(),
    likesByIncident: new Map(),
    commentCountsByIncidentAndUser: new Map(),
  };
}

function sendJson(res, statusCode, payload, cookieValue) {
  const headers = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
  if (cookieValue) {
    headers["Set-Cookie"] = `${COOKIE_NAME}=${cookieValue}; Path=/; HttpOnly; SameSite=Lax`;
  }
  res.writeHead(statusCode, headers);
  res.end(JSON.stringify(payload));
}

function sendSvg(res) {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
      <rect width="640" height="360" fill="#0f172a" />
      <path d="M0 250 L640 110" stroke="#38bdf8" stroke-width="8" opacity="0.7" />
      <path d="M90 0 L210 360" stroke="#ef4444" stroke-width="6" opacity="0.5" />
      <circle cx="320" cy="180" r="24" fill="#fbbf24" />
      <text x="320" y="215" text-anchor="middle" fill="#e2e8f0" font-size="24" font-family="monospace">
        Fixture Map
      </text>
    </svg>
  `;
  res.writeHead(200, {
    "Content-Type": "image/svg+xml",
    "Access-Control-Allow-Origin": "*",
  });
  res.end(svg);
}

function parseCookies(req) {
  const raw = req.headers.cookie || "";
  return Object.fromEntries(
    raw
      .split(";")
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => {
        const [key, ...rest] = part.split("=");
        return [key, rest.join("=")];
      }),
  );
}

function getOrCreateUuid(req) {
  const cookies = parseCookies(req);
  return cookies[COOKIE_NAME] || randomUUID();
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (chunk) => {
      data += chunk;
    });
    req.on("end", () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch (error) {
        reject(error);
      }
    });
    req.on("error", reject);
  });
}

export function createMockApiHandler() {
  let state = createState();

  function getIncidentOrNull(incidentId) {
    return state.incidents.find((incident) => incident.incident_no === incidentId) || null;
  }

  return async (req, res) => {
    const url = new URL(req.url, "http://localhost");
    const cookieValue = getOrCreateUuid(req);

    if (req.method === "OPTIONS") {
      return sendJson(res, 204, {});
    }

    if (req.method === "POST" && url.pathname === "/__reset") {
      state = createState();
      return sendJson(res, 200, { ok: true }, cookieValue);
    }

    if (req.method === "GET" && url.pathname === "/health") {
      return sendJson(res, 200, { ok: true }, cookieValue);
    }

    if (req.method === "GET" && url.pathname === "/api/incidents") {
      const incidents = filterIncidents(state.incidents, url.searchParams).map((incident) => ({
        ...incident,
        liked_by_user: state.likesByIncident.get(incident.incident_no)?.has(cookieValue) ?? false,
      }));
      return sendJson(res, 200, incidents, cookieValue);
    }

    if (req.method === "GET" && url.pathname === "/api/incident_stats") {
      return sendJson(res, 200, buildStats(state.incidents, url.searchParams), cookieValue);
    }

    if (req.method === "GET" && url.pathname === "/api/user/check") {
      return sendJson(res, 200, { uuid: cookieValue }, cookieValue);
    }

    if (req.method === "GET" && url.pathname.startsWith("/maps/")) {
      return sendSvg(res);
    }

    const likeMatch = url.pathname.match(/^\/api\/incidents\/([^/]+)\/like$/);
    if (likeMatch) {
      const incidentId = likeMatch[1];
      const incident = getIncidentOrNull(incidentId);
      if (!incident) {
        return sendJson(res, 404, { error: "Incident not found." }, cookieValue);
      }

      const likedDevices = state.likesByIncident.get(incidentId) || new Set();

      if (req.method === "POST") {
        if (likedDevices.has(cookieValue)) {
          return sendJson(res, 400, { error: "You already liked this post." }, cookieValue);
        }
        likedDevices.add(cookieValue);
        state.likesByIncident.set(incidentId, likedDevices);
        incident.likes += 1;
        return sendJson(res, 200, { likes: incident.likes, liked_by_user: likedDevices.has(cookieValue) }, cookieValue);
      }

      if (req.method === "DELETE") {
        if (likedDevices.has(cookieValue)) {
          likedDevices.delete(cookieValue);
          incident.likes = Math.max(incident.likes - 1, 0);
        }
        state.likesByIncident.set(incidentId, likedDevices);
        return sendJson(res, 200, { likes: incident.likes, liked_by_user: likedDevices.has(cookieValue) }, cookieValue);
      }
    }

    const commentMatch = url.pathname.match(/^\/api\/incidents\/([^/]+)\/comment$/);
    if (commentMatch && req.method === "POST") {
      const incidentId = commentMatch[1];
      const incident = getIncidentOrNull(incidentId);
      if (!incident) {
        return sendJson(res, 404, { error: "Incident not found." }, cookieValue);
      }

      try {
        const body = await readBody(req);
        const comment = String(body.comment || "").trim();
        const username = String(body.username || "Anonymous").trim() || "Anonymous";
        const timestamp = body.timestamp || new Date().toISOString();

        if (comment.length > 150) {
          return sendJson(res, 400, { error: "Comment must be 150 characters or fewer." }, cookieValue);
        }

        if (!comment) {
          return sendJson(res, 400, { error: "Empty comment" }, cookieValue);
        }

        const counterKey = `${incidentId}:${cookieValue}`;
        const count = state.commentCountsByIncidentAndUser.get(counterKey) || 0;
        if (count >= 2) {
          return sendJson(
            res,
            400,
            { error: "You can only leave 2 comments per post." },
            cookieValue,
          );
        }

        state.commentCountsByIncidentAndUser.set(counterKey, count + 1);
        incident.comments.push({ username, comment, timestamp });
        return sendJson(res, 200, { comments: incident.comments }, cookieValue);
      } catch (error) {
        return sendJson(res, 400, { error: "Could not process comment." }, cookieValue);
      }
    }

    return sendJson(res, 404, { error: "Not found" }, cookieValue);
  };
}
