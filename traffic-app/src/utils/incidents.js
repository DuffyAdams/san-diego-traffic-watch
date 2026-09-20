import { formatDateKey, t } from "./i18n.js";
import { buildIncidentImagePath, formatTimestamp } from "./helpers.js";

export function fuzzyMatch(query, text) {
  if (!query) return true;
  if (!text) return false;

  const normalizedQuery = query.toLowerCase();
  const normalizedText = text.toLowerCase();
  if (normalizedText.includes(normalizedQuery)) return true;

  return normalizedQuery
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => normalizedText.includes(word));
}

/**
 * Convert an API incident into the UI's post shape while preserving local UI state.
 *
 * @param {Record<string, any>} incident
 * @param {Record<string, any>} [existingPost={}]
 */
export function buildPostFromIncident(incident, existingPost = {}) {
  const timestamp = incident.timestamp || existingPost.timestamp || "";
  const date = formatDateKey(timestamp);

  return {
    id: incident.incident_no ?? existingPost.id,
    compositeId: `${incident.incident_no}-${date}`,
    details: Array.isArray(incident.Details) ? incident.Details : [],
    timestamp,
    time: formatTimestamp(timestamp),
    description: incident.description || t("fallback.descriptionUnavailable"),
    showFullDescription: existingPost.showFullDescription ?? false,
    location: incident.location || t("fallback.unknownLocation"),
    neighborhood: incident.neighborhood || "",
    latitude: incident.latitude ?? null,
    longitude: incident.longitude ?? null,
    image: buildIncidentImagePath(incident.map_filename),
    likes: typeof incident.likes === "number" ? incident.likes : existingPost.likes ?? 0,
    comments: Array.isArray(incident.comments)
      ? incident.comments
      : existingPost.comments ?? [],
    newComment: existingPost.newComment ?? "",
    showComments: existingPost.showComments ?? false,
    type: incident.type || t("fallback.trafficIncident"),
    likeError: existingPost.likeError ?? "",
    commentError: existingPost.commentError ?? "",
    likeErrorAnimation: existingPost.likeErrorAnimation ?? false,
    active: Boolean(incident.active),
    liking: existingPost.liking ?? false,
    severity: incident.severity ?? null,
    likedByUser:
      typeof incident.liked_by_user === "boolean"
        ? incident.liked_by_user
        : existingPost.likedByUser ?? false,
  };
}

// Preserve unchanged object identities and local state during background refresh.
export function reconcileIncidents(posts, incidents) {
  const byKey = new Map(posts.map((post, index) => [post.compositeId, index]));
  const merged = [...posts];
  const additions = [];
  let changed = false;

  for (const incident of incidents) {
    if (!incident?.incident_no || !incident.timestamp) continue;
    const key = `${incident.incident_no}-${formatDateKey(incident.timestamp)}`;
    const index = byKey.get(key);
    const previous = index === undefined ? undefined : merged[index];
    const next = buildPostFromIncident(incident, previous);
    // An older poll must not undo an optimistic like while its write is pending.
    if (previous?.liking) {
      next.likes = previous.likes;
      next.likedByUser = previous.likedByUser;
    }
    if (!previous) {
      byKey.set(key, merged.length);
      merged.push(next);
      additions.push(next);
      changed = true;
    } else if (Object.keys(next).some((field) =>
      Array.isArray(next[field])
        ? JSON.stringify(next[field]) !== JSON.stringify(previous[field])
        : next[field] !== previous[field],
    )) {
      merged[index] = next;
      changed = true;
    }
  }
  if (!changed) return { posts, additions };
  if (additions.length) merged.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  return { posts: merged, additions };
}
