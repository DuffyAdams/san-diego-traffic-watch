const statusPill = document.getElementById("status-pill");
const refreshButton = document.getElementById("refresh-button");
const lastUpdated = document.getElementById("last-updated");
const selectedRangeLabel = document.getElementById("selected-range-label");
const trafficPosture = document.getElementById("traffic-posture");
const scrapeHealth = document.getElementById("scrape-health");
const trendTitle = document.getElementById("trend-title");
const trendNote = document.getElementById("trend-note");
const loadRatio = document.getElementById("load-ratio");
const loadExplainer = document.getElementById("load-explainer");
const loadMeterFill = document.getElementById("load-meter-fill");
const comparisonBars = document.getElementById("comparison-bars");
const trendChart = document.getElementById("trend-chart");
const typeList = document.getElementById("type-list");
const locationList = document.getElementById("location-list");

const metrics = {
  incidentsInRange: document.getElementById("incidents-in-range"),
  activeIncidents: document.getElementById("active-incidents"),
  trafficVisitors: document.getElementById("traffic-visitors"),
  trafficRequests: document.getElementById("traffic-requests"),
  requestsPerMinute: document.getElementById("requests-per-minute"),
  lastSuccessfulScrape: document.getElementById("last-successful-scrape"),
  siteStatus: document.getElementById("site-status"),
  siteLatency: document.getElementById("site-latency"),
  apiStatus: document.getElementById("api-status"),
  apiLatency: document.getElementById("api-latency"),
  scrapeFreshness: document.getElementById("scrape-freshness"),
  scrapeFreshnessNote: document.getElementById("scrape-freshness-note"),
  processUptime: document.getElementById("process-uptime"),
  processStarted: document.getElementById("process-started"),
  commentsInRange: document.getElementById("comments-in-range"),
  likesInRange: document.getElementById("likes-in-range"),
  engagementActions: document.getElementById("engagement-actions"),
  metricsVisitors: document.getElementById("metrics-visitors"),
};

const labels = {
  incidentsRange: document.getElementById("incidents-range-label"),
  incidentsRangeNote: document.getElementById("incidents-range-note"),
};

const rangeButtons = Array.from(document.querySelectorAll(".range-button"));
let currentRange = "day";
let refreshTimer = null;
let inFlight = false;

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function formatDecimal(value) {
  return Number(value || 0).toFixed(1);
}

function formatLatency(value) {
  return value == null ? "No response" : `${Math.round(Number(value))} ms`;
}

function formatDuration(seconds) {
  const total = Number(seconds || 0);
  if (total < 60) return `${Math.round(total)}s`;
  const minutes = Math.floor(total / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  if (days > 0) return `${days}d ${hours % 24}h`;
  if (hours > 0) return `${hours}h ${minutes % 60}m`;
  return `${minutes}m`;
}

function setStatus(text, tone = "default") {
  statusPill.textContent = text;
  statusPill.dataset.tone = tone;
}

function setRange(range) {
  currentRange = range;
  for (const button of rangeButtons) {
    button.classList.toggle("is-active", button.dataset.range === range);
  }
}

function renderMetric(el, value) {
  el.textContent = value;
}

function classifyTrafficLoad(current, baseline, range) {
  if (range !== "day" || !baseline || baseline <= 0) {
    return {
      label: "Contextual",
      tone: "default",
      ratio: 1,
      copy: "Baseline comparison is only applied to the 24 hour view.",
    };
  }

  const ratio = current / baseline;
  if (ratio >= 1.45) {
    return {
      label: "Elevated",
      tone: "warn",
      ratio,
      copy: `Current hour is running ${formatDecimal((ratio - 1) * 100)} percent above baseline.`,
    };
  }
  if (ratio <= 0.75) {
    return {
      label: "Light",
      tone: "live",
      ratio,
      copy: `Current hour is ${formatDecimal((1 - ratio) * 100)} percent below baseline.`,
    };
  }
  return {
    label: "Nominal",
    tone: "live",
    ratio,
    copy: "Current hour is tracking close to the historical baseline.",
  };
}

function buildRangeLabels(range, count, generatedAt) {
  const end = generatedAt ? new Date(generatedAt) : new Date();
  if (range === "day") {
    return Array.from({ length: count }, (_, index) => {
      const date = new Date(end.getTime() - (count - 1 - index) * 60 * 60 * 1000);
      return date.toLocaleTimeString([], { hour: "numeric" });
    });
  }
  if (range === "week") {
    return Array.from({ length: count }, (_, index) => {
      const date = new Date(end.getTime() - (count - 1 - index) * 24 * 60 * 60 * 1000);
      return date.toLocaleDateString([], { weekday: "short" });
    });
  }
  if (range === "month") {
    return Array.from({ length: count }, (_, index) => {
      const date = new Date(end.getTime() - (count - 1 - index) * 24 * 60 * 60 * 1000);
      return date.toLocaleDateString([], { month: "short", day: "numeric" });
    });
  }
  return Array.from({ length: count }, (_, index) => {
    const date = new Date(end);
    date.setMonth(end.getMonth() - (count - 1 - index));
    return date.toLocaleDateString([], { month: "short" });
  });
}

function renderTrendChart(values = [], chartLabels = [], baseline = null, showBaseline = false) {
  const width = 900;
  const height = 260;
  const padLeft = 40;
  const padRight = 14;
  const padTop = 16;
  const padBottom = 30;
  const chartWidth = width - padLeft - padRight;
  const chartHeight = height - padTop - padBottom;
  const series = Array.isArray(values) ? values.map((n) => Number(n) || 0) : [];

  if (!series.length) {
    trendChart.innerHTML = "";
    return;
  }

  const maxValue = Math.max(...series, showBaseline ? Number(baseline || 0) : 0, 1);
  const points = series.map((value, index) => {
    const x = padLeft + (index / Math.max(series.length - 1, 1)) * chartWidth;
    const y = padTop + chartHeight - (value / maxValue) * chartHeight;
    return { x, y, value };
  });

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");
  const areaPath = `${linePath} L ${points.at(-1).x.toFixed(2)} ${(height - padBottom).toFixed(2)} L ${points[0].x.toFixed(2)} ${(height - padBottom).toFixed(2)} Z`;
  const gridLines = Array.from({ length: 4 }, (_, idx) => {
    const y = padTop + (chartHeight / 3) * idx;
    const label = Math.round(maxValue - (maxValue / 3) * idx);
    return `
      <line class="chart-grid-line" x1="${padLeft}" y1="${y}" x2="${width - padRight}" y2="${y}"></line>
      <text class="chart-value-label" x="4" y="${y + 4}">${label}</text>
    `;
  }).join("");

  const desiredTicks = series.length <= 8 ? series.length : 6;
  const step = Math.max(Math.floor((series.length - 1) / Math.max(desiredTicks - 1, 1)), 1);
  const tickIndexes = Array.from({ length: series.length }, (_, idx) => idx)
    .filter((idx) => idx === 0 || idx === series.length - 1 || idx % step === 0)
    .slice(0, desiredTicks + 1);
  const axisLabels = Array.from(new Set(tickIndexes)).map((idx) => {
    const label = chartLabels[idx] || "";
    return `<text class="chart-axis-label" x="${points[idx].x}" y="${height - 8}" text-anchor="middle">${label}</text>`;
  }).join("");

  const baselinePath = showBaseline
    ? `<path class="chart-baseline" d="M ${padLeft} ${(padTop + chartHeight - (Number(baseline || 0) / maxValue) * chartHeight).toFixed(2)} L ${width - padRight} ${(padTop + chartHeight - (Number(baseline || 0) / maxValue) * chartHeight).toFixed(2)}"></path>`
    : "";

  const lastPoint = points.at(-1);
  trendChart.innerHTML = `
    <defs>
      <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="rgba(49, 130, 206, 0.24)"></stop>
        <stop offset="100%" stop-color="rgba(49, 130, 206, 0.02)"></stop>
      </linearGradient>
    </defs>
    ${gridLines}
    <path class="chart-area" d="${areaPath}"></path>
    ${baselinePath}
    <path class="chart-line" d="${linePath}"></path>
    <circle class="chart-last-dot" cx="${lastPoint.x}" cy="${lastPoint.y}" r="4.5"></circle>
    ${axisLabels}
  `;
}

function renderList(container, values = {}, limit = 7) {
  const entries = Object.entries(values || {}).slice(0, limit);
  const max = Math.max(...entries.map(([, count]) => Number(count) || 0), 1);

  container.innerHTML = entries.length
    ? entries
        .map(([name, count]) => {
          const numericCount = Number(count) || 0;
          const width = Math.max((numericCount / max) * 100, numericCount > 0 ? 10 : 0);
          return `
            <article class="list-item">
              <div class="list-row">
                <span class="list-name">${name}</span>
                <span class="list-count">${formatNumber(numericCount)}</span>
              </div>
              <div class="list-bar"><span style="width:${width}%"></span></div>
            </article>
          `;
        })
        .join("")
    : `<article class="list-item"><div class="list-row"><span class="list-name">No data yet</span><span class="list-count">-</span></div></article>`;
}

function renderComparisonBars(items) {
  const max = Math.max(...items.map((item) => item.value), 1);
  comparisonBars.innerHTML = items
    .map((item) => {
      const width = Math.max((item.value / max) * 100, item.value > 0 ? 8 : 0);
      return `
        <article class="bar-item">
          <div class="bar-head">
            <span class="bar-label">${item.label}</span>
            <span class="list-count">${item.formatted}</span>
          </div>
          <div class="bar-track"><span class="bar-fill" style="width:${width}%"></span></div>
        </article>
      `;
    })
    .join("");
}

function renderProbe(statusEl, latencyEl, probe) {
  if (!probe || !probe.ok) {
    statusEl.textContent = "Down";
    latencyEl.textContent = probe && probe.error ? probe.error : "No response";
    return false;
  }

  statusEl.textContent = `HTTP ${probe.statusCode}`;
  latencyEl.textContent = formatLatency(probe.latencyMs);
  return true;
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`${url} failed with ${response.status}`);
  }
  return response.json();
}

async function loadDashboard() {
  if (inFlight) return;
  inFlight = true;
  setStatus("Refreshing", "default");

  try {
    const query = `date_filter=${encodeURIComponent(currentRange)}`;
    const [dashboard, stats] = await Promise.all([
      fetchJson(`/api/dashboard_metrics?${query}`),
      fetchJson(`/api/incident_stats?${query}`),
    ]);

    const ai = dashboard.llmUsage;
    if (ai) {
      document.getElementById("ai-cost").textContent = ai.reportedCost == null ? (ai.attempts ? "Unknown" : "$0.00") : `$${Number(ai.reportedCost).toFixed(4)}${ai.missingCost ? " + unknown" : ""}`;
      document.getElementById("ai-attempts").textContent = `${formatNumber(ai.attempts)} attempts · ${formatNumber(ai.staleResults)} stale results`;
      document.getElementById("ai-tokens").textContent = ai.inputTokens == null || ai.completionTokens == null ? (ai.attempts ? "Unknown" : "0") : `${formatNumber(ai.inputTokens + ai.completionTokens)}${ai.missingUsage ? " + unknown" : ""}`;
      document.getElementById("ai-reasoning").textContent = ai.reasoningTokens == null ? "Reasoning usage unavailable" : `${formatNumber(ai.reasoningTokens)} reasoning tokens included`;
      document.getElementById("ai-pending").textContent = `${formatNumber(ai.jobs?.pending)} pending`;
      document.getElementById("ai-failed").textContent = `${formatNumber(ai.jobs?.failed)} need attention · ${formatNumber(ai.templates)} stored templates`;
    }

    const rangeLabel = dashboard.rangeLabel || stats.rangeLabel || "Selected range";
    const rangeKey = dashboard.rangeKey || currentRange;
    const series = Array.isArray(stats.hourlyData) ? stats.hourlyData.map(Number) : [];
    const chartLabels = buildRangeLabels(rangeKey, series.length, stats.generatedAt || dashboard.generatedAt);
    const currentValue = series.at(-1) || 0;
    const load = classifyTrafficLoad(currentValue, stats.historicalCurrentHourAverage || 0, rangeKey);
    const meterWidth = rangeKey === "day" ? Math.max(8, Math.min(load.ratio * 48, 100)) : 34;

    labels.incidentsRange.textContent = `${rangeLabel} incidents`;
    labels.incidentsRangeNote.textContent = `${formatNumber(dashboard.totalIncidentsIngested)} incidents tracked overall.`;
    selectedRangeLabel.textContent = rangeLabel;
    trendTitle.textContent = `${rangeLabel} incident volume`;

    renderMetric(metrics.incidentsInRange, formatNumber(dashboard.incidentsInRange));
    renderMetric(metrics.activeIncidents, formatNumber(dashboard.activeIncidents));
    renderMetric(metrics.trafficVisitors, formatNumber(dashboard.trafficAppUniqueVisitorsInRange));
    renderMetric(metrics.trafficRequests, formatNumber(dashboard.trafficAppRequestsInRange));
    renderMetric(metrics.requestsPerMinute, formatDecimal(dashboard.requestsPerMinute));
    renderMetric(metrics.lastSuccessfulScrape, dashboard.lastSuccessfulScrape || "No successful scrape yet");
    renderMetric(metrics.commentsInRange, formatNumber(dashboard.commentsInRange));
    renderMetric(metrics.likesInRange, formatNumber(dashboard.likesInRange));
    renderMetric(metrics.engagementActions, formatNumber(dashboard.engagementActionsInRange));
    renderMetric(metrics.metricsVisitors, formatNumber(dashboard.metricsPageUniqueVisitorsInRange));
    renderMetric(metrics.scrapeFreshness, dashboard.scrapeHealthStatus || "Unknown");
    renderMetric(metrics.processUptime, formatDuration(dashboard.processUptimeSeconds));
    renderMetric(metrics.processStarted, dashboard.processStartedAt ? new Date(dashboard.processStartedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "Unknown");
    renderMetric(metrics.scrapeFreshnessNote, dashboard.scrapeFreshnessSeconds == null ? "No scrape timestamp" : `${formatDuration(dashboard.scrapeFreshnessSeconds)} since last success`);

    const siteOk = renderProbe(metrics.siteStatus, metrics.siteLatency, dashboard.publicSiteHealth);
    const apiOk = renderProbe(metrics.apiStatus, metrics.apiLatency, dashboard.publicApiHealth);

    trafficPosture.textContent = load.label;
    scrapeHealth.textContent = dashboard.scrapeHealthStatus || "Unknown";
    lastUpdated.textContent = new Date(dashboard.generatedAt || Date.now()).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
    });

    loadRatio.textContent = rangeKey === "day"
      ? `${formatDecimal(load.ratio)}x baseline`
      : `${formatNumber(currentValue)} latest bucket`;
    loadExplainer.textContent = load.copy;
    loadMeterFill.style.width = `${meterWidth}%`;

    renderTrendChart(
      series,
      chartLabels,
      stats.historicalCurrentHourAverage || 0,
      rangeKey === "day",
    );
    renderList(typeList, stats.incidentsByType || {}, 7);
    renderList(locationList, stats.topLocations || {}, 7);
    renderComparisonBars([
      {
        label: `${rangeLabel} traffic-app requests`,
        value: Number(dashboard.trafficAppRequestsInRange) || 0,
        formatted: formatNumber(dashboard.trafficAppRequestsInRange),
      },
      {
        label: `${rangeLabel} traffic-app visitors`,
        value: Number(dashboard.trafficAppUniqueVisitorsInRange) || 0,
        formatted: formatNumber(dashboard.trafficAppUniqueVisitorsInRange),
      },
      {
        label: `${rangeLabel} engagement actions`,
        value: Number(dashboard.engagementActionsInRange) || 0,
        formatted: formatNumber(dashboard.engagementActionsInRange),
      },
      {
        label: "Runtime requests served",
        value: Number(dashboard.apiRequestsServed) || 0,
        formatted: formatNumber(dashboard.apiRequestsServed),
      },
    ]);

    trendNote.textContent = rangeKey === "day"
      ? `${formatNumber(stats.eventsLastHour || 0)} incidents in the last hour, ${formatDecimal(stats.historicalCurrentHourAverage || 0)} baseline.`
      : `${formatNumber(currentValue)} incidents in the most recent bucket of ${rangeLabel.toLowerCase()}.`;

    const tone = !siteOk || !apiOk ? "error" : (dashboard.scrapeHealthStatus === "Healthy" ? "live" : "warn");
    setStatus(`Live ${rangeLabel}`, tone);
  } catch (error) {
    console.error(error);
    setStatus("Unavailable", "error");
    trafficPosture.textContent = "Unavailable";
    scrapeHealth.textContent = "Unavailable";
    trendNote.textContent = "Unable to load live metrics right now.";
    loadRatio.textContent = "--";
    loadExplainer.textContent = "The dashboard could not retrieve the latest operational data.";
    loadMeterFill.style.width = "0%";
  } finally {
    inFlight = false;
  }
}

for (const button of rangeButtons) {
  button.addEventListener("click", () => {
    const nextRange = button.dataset.range || "day";
    if (nextRange === currentRange) return;
    setRange(nextRange);
    loadDashboard();
  });
}

refreshButton.addEventListener("click", loadDashboard);
setRange(currentRange);
loadDashboard();
refreshTimer = setInterval(loadDashboard, 15000);
window.addEventListener("beforeunload", () => {
  if (refreshTimer) clearInterval(refreshTimer);
});
