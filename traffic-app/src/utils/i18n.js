import { writable } from "svelte/store";

const DEFAULT_LOCALE = "en-US";
const LOCALE_STORAGE_KEY = "trafficAppLocale";

export const locale = writable(DEFAULT_LOCALE);

let currentLocale = DEFAULT_LOCALE;
locale.subscribe((value) => {
  currentLocale = normalizeLocale(value);
  if (typeof document !== "undefined") {
    document.documentElement.lang = currentLocale;
    document.documentElement.dir = "ltr";
  }
});

const messages = {
  en: {
    app: {
      name: "San Diego Traffic Watch",
    },
    header: {
      brandTitle: "San Diego Watch",
      brandSubtitle: "",
      feedStatus: ({ time }) => time,
      monitoringIncidents: "",
      systemDiagnostics: "Stats",
      statistics: "Stats",
      switchToLightMode: "Switch to light mode",
      switchToDarkMode: "Switch to dark mode",
      enableAccessibilityMode: "Enable accessibility mode",
      disableAccessibilityMode: "Disable accessibility mode",
    },
    filters: {
      all: "All",
      traffic: "Traffic",
      sdpd: "SDPD",
      sheriff: "Sheriff",
      fire: "Fire",
      map: "Map",
    },
    table: {
      type: "Type",
      time: "Time",
      location: "Location",
      status: "Status",
    },
    search: {
      placeholder: "Search incidents...",
      ariaLabel: "Search incidents",
      clear: "Clear search",
    },
    view: {
      tableView: "Table view",
      cardView: "Card view",
      expandToCardView: "Expand to card view",
      condenseToTableView: "Condense to table view",
      cards: "Cards",
      table: "Table",
    },
    actions: {
      like: "Like",
      comment: "Comment",
      share: "Share",
      send: "Send",
      details: "Details",
      viewRawDetails: "View raw details",
      rawEventDetails: "Raw event details",
      resetTypeFilters: "Reset type filters",
      resetLocationFilters: "Reset location filters",
      closeComments: "Close comments",
      expandDescription: "Expand description",
      collapseDescription: "Collapse description",
    },
    comments: {
      title: ({ count }) => `Comments (${formatNumber(count)})`,
      empty: "Be the first to comment.",
      placeholder: "Write a comment...",
    },
    status: {
      active: "Active",
      inactive: "Inactive",
      live: "Live",
      noData: "No data",
      highActivity: "High activity",
      insufficientHistory: "Building baseline",
      historyNeeded: "At least 3 matching hours from prior weeks are needed to compare activity.",
      activityComparison: ({ current, average, samples }) =>
        `Last hour: ${formatNumber(current)} incidents · Usual: ${formatNumber(average, { maximumFractionDigits: 1 })} · Based on ${formatNumber(samples)} matching hours from the past 8 weeks.`,
      elevatedIncidents: "Elevated incidents",
      lightIncidents: "Light incidents",
      nominal: "Typical activity",
      error: "Error",
    },
    diagnostics: {
      today: "Today",
      lastHour: "Last hour",
      active: "Active",
      total: "Total",
      timePeriod: "Time period",
      oneDay: "1 day",
      week: "Week",
      month: "Month",
      year: "Year",
      activity24Hours: "24-hour activity",
      current24Hours: "Current",
      previousWeek24Hours: "Last week",
      previousWeekUnavailable: "Last week unavailable",
      current7Days: "Current",
      current30Days: "Current",
      current12Months: "Current",
      previous7Days: "Previous",
      previous30Days: "Previous",
      previous12Months: "Previous",
      previousPeriodUnavailable: "Previous period unavailable",
      periodComparison: ({ time, current, previous, currentLabel, previousLabel }) =>
        `${time}: ${currentLabel}: ${formatNumber(current)} incidents; ${previousLabel}: ${formatNumber(previous)} incidents.`,
      activity7Days: "7-day activity",
      activity30Days: "30-day activity",
      yearlyActivity: "Yearly activity",
      byType: "By type",
      topLocations: "Top locations",
      noActivityData: "No activity data available.",
      incidentsCount: ({ count }) => `${formatNumber(count)} ${pluralize("incident", count)}`,
    },
    fallback: {
      recent: "Recent",
      descriptionUnavailable: "No description available",
      unknownLocation: "Unknown location",
      incidentType: "Incident",
      trafficIncident: "Traffic incident",
      noDataAvailable: "No data available.",
      notAvailable: "N/A",
      error: "Error",
    },
    state: {
      loadingMap: "Loading map...",
      mapUnavailable: "Map preview unavailable",
      noIncidentsTitle: "No incidents to display at the moment.",
      noIncidentsSubtitle: "Check back soon for updates.",
      noSearchTitle: "No incidents match your search.",
      noSearchSubtitle: "Try adjusting your query or loading more posts.",
      moreIncidentsAvailable: "More incidents available",
      loadIncidentsUnavailable: "Unable to load incidents at this time.",
    },
    share: {
      title: "Share incident",
      close: "Close share preview",
      preparing: "Preparing card image…",
      previewAlt: ({ location }) => `Incident card at ${location}`,
      download: "Download image",
      imageFailed: "Could not create the card image. You can still share the incident text and link.",
      shareFailed: "Could not share the incident. Please try again.",
      incidentSummary: ({ description, location }) =>
        `${description} - Location: ${location}. Check out more traffic incidents at San Diego Traffic Watch.`,
    },
    toast: {
      offline: "You are offline. Some features may not work.",
      connectionRestored: "Connection restored.",
      failedLoadIncidents: "Failed to load incidents. Please check your connection and try again.",
      invalidIncidentData: "Received invalid data from server.",
      failedLoadIncidentStats: "Failed to load incident statistics.",
      failedLikePost: "Failed to like post. Please try again.",
      failedUnlikePost: "Failed to unlike post. Please try again.",
      commentLimitReached: "You can only leave 2 comments per post.",
      commentAdded: "Comment added successfully!",
      failedSubmitComment: "Failed to submit comment. Please try again.",
      newIncidents: ({ count }) => `${formatNumber(count)} new ${pluralize("incident", count)}`,
    },
  },
};

function normalizeLocale(value) {
  if (!value || typeof value !== "string") return DEFAULT_LOCALE;
  try {
    return Intl.getCanonicalLocales(value)[0] || DEFAULT_LOCALE;
  } catch {
    return DEFAULT_LOCALE;
  }
}

function resolveMessages(value) {
  const normalized = normalizeLocale(value);
  const base = normalized.split("-")[0];
  return messages[normalized] || messages[base] || messages.en;
}

function getCurrentMessages() {
  return resolveMessages(currentLocale);
}

function lookupMessage(dictionary, key) {
  return key.split(".").reduce((acc, segment) => {
    if (acc && typeof acc === "object" && segment in acc) {
      return acc[segment];
    }
    return undefined;
  }, dictionary);
}

function interpolate(template, values) {
  return template.replace(/\{(\w+)\}/g, (_, key) => String(values[key] ?? ""));
}

function pluralize(singular, count, plural = `${singular}s`) {
  return Math.abs(Number(count)) === 1 ? singular : plural;
}

function toDate(value) {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function initializeLocale(preferredLocale) {
  const detected = preferredLocale || (typeof window !== "undefined"
    ? localStorage.getItem(LOCALE_STORAGE_KEY) || navigator.languages?.find(Boolean) || navigator.language
    : DEFAULT_LOCALE);
  const nextLocale = normalizeLocale(detected);
  locale.set(nextLocale);
  if (typeof window !== "undefined") {
    localStorage.setItem(LOCALE_STORAGE_KEY, nextLocale);
  }
  return nextLocale;
}

export function t(key, values = {}) {
  const entry =
    lookupMessage(getCurrentMessages(), key) ??
    lookupMessage(messages.en, key) ??
    key;

  if (typeof entry === "function") {
    return entry(values);
  }

  return interpolate(String(entry), values);
}

const formatters = new Map();

function getFormatter(kind, options) {
  const key = JSON.stringify([currentLocale, kind, options]);
  if (!formatters.has(key)) {
    if (formatters.size >= 64) formatters.delete(formatters.keys().next().value);
    formatters.set(key, new Intl[kind](currentLocale, options));
  }
  return formatters.get(key);
}

export function formatDateTime(value, options = {}) {
  const date = toDate(value);
  if (!date) return "";
  return getFormatter("DateTimeFormat", options).format(date);
}

export function formatNumber(value, options = {}) {
  const numericValue = Number(value ?? 0);
  return getFormatter("NumberFormat", options).format(
    Number.isFinite(numericValue) ? numericValue : 0,
  );
}

export function formatRelativeTimeFromNow(value, options = {}) {
  const date = toDate(value);
  if (!date) return t("fallback.recent");

  const diffSeconds = Math.round((date.getTime() - (options.now ?? Date.now())) / 1000);
  const absSeconds = Math.abs(diffSeconds);
  const formatter = getFormatter("RelativeTimeFormat", {
    numeric: options.numeric || "auto",
    style: options.style || "short",
  });

  if (absSeconds < 60) return formatter.format(diffSeconds, "second");
  const diffMinutes = Math.round(diffSeconds / 60);
  if (Math.abs(diffMinutes) < 60) return formatter.format(diffMinutes, "minute");
  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 24) return formatter.format(diffHours, "hour");
  const diffDays = Math.round(diffHours / 24);
  if (Math.abs(diffDays) < 7) return formatter.format(diffDays, "day");

  return formatDateTime(date, {
    month: "short",
    day: "numeric",
  });
}

export function formatDateKey(value) {
  const date = toDate(value);
  if (!date) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function compareText(a, b) {
  return getFormatter("Collator", {
    numeric: true,
    sensitivity: "base",
  }).compare(a ?? "", b ?? "");
}
