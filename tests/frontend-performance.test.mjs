import test from "node:test";
import assert from "node:assert/strict";
import { buildPostFromIncident, reconcileIncidents } from "../traffic-app/src/utils/incidents.js";
import { formatDateTime, formatRelativeTimeFromNow } from "../traffic-app/src/utils/i18n.js";

const incident = {
  incident_no: "test-1", timestamp: "2026-09-19T12:00:00Z", location: "I-5",
  description: "Traffic hazard", active: true, likes: 2, liked_by_user: false,
  Details: ["Lane closed"], comments: [{ username: "Driver", comment: "Slow traffic" }],
};

test("unchanged refreshes preserve the entire feed and post identities", () => {
  const posts = [buildPostFromIncident(incident)];
  const result = reconcileIncidents(posts, [structuredClone(incident)]);
  assert.equal(result.posts, posts);
  assert.equal(result.posts[0], posts[0]);
  assert.deepEqual(result.additions, []);
});

test("changed incidents preserve open comments, draft text, and pending likes", () => {
  const posts = [{ ...buildPostFromIncident(incident), showComments: true,
    newComment: "My draft", liking: true, likes: 3, likedByUser: true }];
  const result = reconcileIncidents(posts, [{ ...incident, description: "Lane reopened" }]);
  assert.equal(result.posts[0].description, "Lane reopened");
  assert.equal(result.posts[0].showComments, true);
  assert.equal(result.posts[0].newComment, "My draft");
  assert.equal(result.posts[0].likes, 3);
  assert.equal(result.posts[0].likedByUser, true);
});

test("new arrivals stay newest first and duplicate records do not duplicate cards", () => {
  const posts = [buildPostFromIncident(incident)];
  const newer = { ...incident, incident_no: "test-2", timestamp: "2026-09-19T13:00:00Z" };
  const newest = { ...incident, incident_no: "test-3", timestamp: "2026-09-19T14:00:00Z" };
  const result = reconcileIncidents(posts, [newest, newer, newest, null]);
  assert.deepEqual(result.posts.map(p => p.id), ["test-3", "test-2", "test-1"]);
  assert.equal(result.additions.length, 2);
  assert.equal(result.posts[2], posts[0]);
});

test("a reused incident number on another day is a separate incident", () => {
  const posts = [buildPostFromIncident(incident)];
  const result = reconcileIncidents(posts, [{ ...incident, timestamp: "2026-09-20T12:00:00Z" }]);
  assert.equal(result.posts.length, 2);
  assert.notEqual(result.posts[0].compositeId, result.posts[1].compositeId);
});

test("cached formatters preserve options and relative timestamps use the shared clock", () => {
  const date = new Date(incident.timestamp);
  const options = { month: "short", day: "numeric" };
  assert.equal(formatDateTime(date, options), new Intl.DateTimeFormat("en-US", options).format(date));
  assert.equal(formatRelativeTimeFromNow(date, { now: date.getTime() + 30000 }), "30 sec. ago");
  assert.equal(formatRelativeTimeFromNow(date, { now: date.getTime() + 120000 }), "2 min. ago");
});
