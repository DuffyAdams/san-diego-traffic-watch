/**
 * Utility helper functions for the Traffic App
 */
import { formatDateTime, formatRelativeTimeFromNow, t } from "./i18n.js";

// Generate a random username for anonymous users
const adjectives = ["Cool", "Happy", "Swift", "Brave", "Clever", "Lucky"];
const nouns = ["Panda", "Tiger", "Eagle", "Fox", "Wolf", "Bear"];

export function generateRandomUsername() {
    const adj = adjectives[Math.floor(Math.random() * adjectives.length)];
    const noun = nouns[Math.floor(Math.random() * nouns.length)];
    const num = Math.floor(Math.random() * 100);
    return `${adj}${noun}${num}`;
}

// Debounce utility
export function debounce(func, wait) {
    let timeout;
    function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    }
    executedFunction.cancel = () => clearTimeout(timeout);
    return executedFunction;
}

// Retry utility with exponential backoff
export async function retryWithBackoff(fn, maxRetries = 3, baseDelay = 1000) {
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            return await fn();
        } catch (error) {
            if (error && error.name === "AbortError") {
                throw error;
            }
            if (attempt === maxRetries) throw error;
            const delay = baseDelay * Math.pow(2, attempt);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
}

// Format timestamp for display
export function formatTimestamp(timestamp) {
    if (!timestamp) return t("fallback.recent");
    return formatDateTime(timestamp, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
    });
}

// Format time only (for compact display)
export function formatTimeOnly(timestamp) {
    if (!timestamp) return t("fallback.recent");
    return formatDateTime(timestamp, {
        hour: "numeric",
        minute: "2-digit",
    });
}
export const formatTime = formatTimeOnly;

export function buildIncidentImagePath(mapFilename) {
    if (!mapFilename || typeof mapFilename !== "string") return "";

    const trimmed = mapFilename.trim();
    if (!trimmed) return "";

    return trimmed.startsWith("/maps/") ? trimmed : `/maps/${trimmed}`;
}

// Format comment timestamp (relative time)
export function formatCommentTimestamp(timestamp) {
    if (!timestamp) return "";
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    if (diff < 604800000) {
        return formatRelativeTimeFromNow(timestamp, { style: "short" });
    }

    return formatDateTime(timestamp, {
        month: "short",
        day: "numeric"
    });
}

// Truncate description text
export function truncateDescription(text, length = 200) {
    if (!text) return "";
    if (text.length <= length) return text;

    const lastSpaceIndex = text.lastIndexOf(" ", length);
    if (lastSpaceIndex === -1) return text.substring(0, length);

    return text.substring(0, lastSpaceIndex);
}

// Get emoji icon for incident type
export function getIconForIncidentType(type) {
    const types = {
        "Aircraft Emergency": "plane",
        "Animal Hazard": "paw-print",
        "Assist CT with Maintenance": "wrench",
        "Road Closure": "ban",
        "Car Fire": "flame",
        "Construction": "hard-hat",
        "Defective Traffic Signals": "traffic-cone",
        "Fatality": "skull",
        "Hit and Run No Injuries": "car-off",
        "JUMPER": "user-x",
        "Live or Dead Animal": "paw-print",
        "Maintenance": "hammer",
        "Debris From Vehicle": "box",
        "Provide Traffic Control": "shield-alert",
        "Report of Fire": "flame",
        "Request CalTrans Notify": "phone-call",
        "Road Conditions": "road",
        "SIG Alert": "megaphone",
        "SPINOUT": "rotate-ccw",
        "Traffic Break": "hand",
        "Traffic Collision": "car",
        "Traffic Hazard": "triangle-alert",
        "Wrong Way Driver": "arrow-left-right",
        // Police Types
        "AUTO THEFT": "car",
        "MISD HIT/RUN": "car-off",
        "VANDALISM": "alert-circle",
        "ROBBERY": "wallet",
        "SUICIDE-THREATS": "alert-triangle",
        "DISTURBING PEACE": "volume-2",
        "REPORT OF DEATH": "skull",
        "PRISONER IN CUSTODY": "lock",
        "MENTAL CASE": "brain",
        // Sheriff Types
        "ABANDONED VEHICLE": "car-off",
        "REPORT - 459 BURGLARY, VEHICLE": "car",
        "DISTURBANCE": "volume-2",
        // Fire Types
        "MEDICAL": "activity",
        "STRUCTURE FIRE": "flame",
        "VEGETATION FIRE": "trees",
        "TRAFFIC ACCIDENT": "car"
    };
    return types[type] || "siren";
}

// Highlight matched search queries
export function highlightFuzzy(text, query) {
    if (!text) return "";
    const escapedText = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    if (!query || query.trim() === "") return escapedText;

    const q = query.trim().toLowerCase();

    if (escapedText.toLowerCase().includes(q)) {
        const escapedQ = q.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&");
        const regex = new RegExp(`(${escapedQ})`, "gi");
        return escapedText.replace(regex, '<mark class="search-highlight">$1</mark>');
    }

    const words = q.split(/\s+/).filter(Boolean);
    let highlightedText = escapedText;
    for (const word of words) {
        if (word.length > 0) {
            const escapedWord = word.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&");
            const regex = new RegExp(`(${escapedWord})`, "gi");
            highlightedText = highlightedText.replace(regex, '<mark class="search-highlight">$1</mark>');
        }
    }
    return highlightedText;
}
