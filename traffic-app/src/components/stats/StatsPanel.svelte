<script>
    import { onMount, createEventDispatcher } from "svelte";
    import { slide } from "../../utils/motion.js";

    import Calendar from "lucide-svelte/icons/calendar";
    import Clock from "lucide-svelte/icons/clock";
    import Zap from "lucide-svelte/icons/zap";
    import BarChart3 from "lucide-svelte/icons/bar-chart-3";
    import MapPin from "lucide-svelte/icons/map-pin";
    import X from "lucide-svelte/icons/x";
    import IncidentIcon from "../shared/IncidentIcon.svelte";
    import { formatDateTime, formatNumber, t } from "../../utils/i18n.js";

    import { classifyActivity } from "../../utils/activityStatus.js";

    const dispatch = createEventDispatcher();
    export let eventsToday = 0;
    export let eventsLastHour = 0;
    export let eventsActive = 0;
    export let totalIncidents = 0;
    export let timeFilter = "day";
    export let hourlyData = [];
    export let previousWeekHourlyData = null;
    export let incidentsByType = {};
    export let topLocations = {};
    export let selectedTypes = new Set();
    export let selectedLocations = new Set();
    export let historicalCurrentHourAverage = null;
    export let historicalHourSampleCount = 0;
    export let referenceTime = "";

    function parseReferenceTime(value) {
        const fallback = new Date();
        if (!value) return fallback;

        const parsed = new Date(value);
        return Number.isNaN(parsed.getTime()) ? fallback : parsed;
    }

    let currentTime = parseReferenceTime(referenceTime);
    let hoveredIndex = null;

    $: expectedBucketCount =
        timeFilter === "day"
            ? 24
            : timeFilter === "week"
              ? 7
              : timeFilter === "month"
                ? 30
                : 12;
    $: chartData = normalizeChartData(hourlyData, expectedBucketCount);
    // An absent or incomplete comparison is unknown, not zero activity.
    $: comparisonData = timeFilter === "day" &&
        Array.isArray(previousWeekHourlyData) &&
        previousWeekHourlyData.length === 24 &&
        previousWeekHourlyData.every(value => Number.isFinite(value) && value >= 0)
            ? previousWeekHourlyData : [];
    $: hasComparison = comparisonData.length === 24;
    $: typeEntries = Object.entries(incidentsByType);
    $: locationEntries = Object.entries(topLocations);
    $: maxTypeCount = Math.max(...typeEntries.map(([, count]) => count), 1);
    $: maxLocationCount = Math.max(...locationEntries.map(([, count]) => count), 1);

    // Div-based chart computations
    $: maxValue = Math.max(0, ...chartData, ...comparisonData);
    $: yMax = Math.max(maxValue * 1.15, 10);

    $: activityStatus = classifyActivity({
        current: eventsLastHour,
        average: historicalCurrentHourAverage,
        sampleCount: historicalHourSampleCount,
        hasData: Array.isArray(hourlyData) && hourlyData.length > 0,
    });
    $: statusColor = {
        highActivity: "#ef4444",
        elevatedIncidents: "#f59e0b",
        lightIncidents: "var(--text-muted)",
        nominal: "#10b981",
    }[activityStatus] || "var(--text-muted)";
    $: statusExplanation = activityStatus === "noData"
        ? t("diagnostics.noActivityData")
        : activityStatus === "insufficientHistory"
          ? t("status.historyNeeded")
          : t("status.activityComparison", {
                current: eventsLastHour,
                average: historicalCurrentHourAverage,
                samples: historicalHourSampleCount,
            });

    // Update currentTime every minute
    onMount(() => {
        const interval = setInterval(() => {
            currentTime = new Date(currentTime.getTime() + 60000);
        }, 60000);

        return () => {
            clearInterval(interval);
        };
    });

    $: if (referenceTime) {
        currentTime = parseReferenceTime(referenceTime);
    }

    $: sectionTitle =
        timeFilter === "day"
            ? t("diagnostics.activity24Hours")
            : timeFilter === "week"
              ? t("diagnostics.activity7Days")
              : timeFilter === "month"
                ? t("diagnostics.activity30Days")
                : t("diagnostics.yearlyActivity");

    $: chartLabels =
        timeFilter === "day"
            ? Array.from({ length: 24 }, (_, i) => {
                  const time = new Date(
                      currentTime.getTime() - (23 - i) * 60 * 60 * 1000,
                  );
                  return formatDateTime(time, {
                      hour: "numeric",
                  });
              })
            : timeFilter === "week"
              ? Array.from({ length: 7 }, (_, i) => {
                    const date = new Date();
                    date.setDate(date.getDate() - (6 - i));
                    return formatDateTime(date, {
                        weekday: "short",
                    });
                })
              : timeFilter === "month"
                ? Array.from({ length: 30 }, (_, i) => {
                      const date = new Date();
                      date.setDate(date.getDate() - (29 - i));
                      return formatDateTime(date, {
                          day: "numeric",
                      });
                  })
                : Array.from({ length: 12 }, (_, i) => {
                      const date = new Date();
                      date.setDate(1);
                      date.setMonth(currentTime.getMonth() - (11 - i));
                      return formatDateTime(date, {
                          month: "short",
                      });
                  });

    function normalizeChartData(values, expectedLength) {
        const data = Array.isArray(values) ? values.map(Number) : [];
        if (data.length === 0) return [];
        if (data.length === expectedLength) return data;
        if (data.length > expectedLength) return data.slice(data.length - expectedLength);
        return [...Array(expectedLength - data.length).fill(0), ...data];
    }

    function setTimeFilter(newFilter) {
        dispatch("filterTime", newFilter);
    }

    function filterByType(type) {
        dispatch("filterType", type);
    }

    function filterByLocation(location) {
        dispatch("filterLocation", location);
    }

    function resetTypeFilters() {
        dispatch("resetTypeFilters");
    }

    function resetLocationFilters() {
        dispatch("resetLocationFilters");
    }
</script>

<div class="event-counters">
    <div class="top-row">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon"><Calendar size={24} /></div>
                <div class="stat-value">{formatNumber(eventsToday)}</div>
                <div class="stat-label">{t("diagnostics.today")}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><Clock size={24} /></div>
                <div class="stat-value">{formatNumber(eventsLastHour)}</div>
                <div class="stat-label">{t("diagnostics.lastHour")}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><Zap size={24} /></div>
                <div class="stat-value">{formatNumber(eventsActive)}</div>
                <div class="stat-label">{t("diagnostics.active")}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><BarChart3 size={24} /></div>
                <div class="stat-value">{formatNumber(totalIncidents)}</div>
                <div class="stat-label">{t("diagnostics.total")}</div>
            </div>
        </div>
        <div class="time-period-section">
            <span class="section-label" id="stats-time-period">{t("diagnostics.timePeriod")}</span>
            <div class="time-buttons" role="group" aria-labelledby="stats-time-period">
                <button
                    class="time-button"
                    class:active={timeFilter === "day"}
                    on:click={() => setTimeFilter("day")}>{t("diagnostics.oneDay")}</button
                >
                <button
                    class="time-button"
                    class:active={timeFilter === "week"}
                    on:click={() => setTimeFilter("week")}>{t("diagnostics.week")}</button
                >
                <button
                    class="time-button"
                    class:active={timeFilter === "month"}
                    on:click={() => setTimeFilter("month")}>{t("diagnostics.month")}</button
                >
                <button
                    class="time-button"
                    class:active={timeFilter === "year"}
                    on:click={() => setTimeFilter("year")}>{t("diagnostics.year")}</button
                >
            </div>
        </div>
    </div>

    <!-- Activity Chart -->
    <div class="activity-chart-section">
        <div class="activity-header">
            <span class="section-title">{sectionTitle}</span>
            {#if timeFilter === "day"}
                <div class="status-indicator" role="status">
                    <span class="status-dot" style="background-color: {statusColor};"></span>
                    <span class="status-text" style="color: {statusColor};"
                        >{t(`status.${activityStatus}`)}</span>
                </div>
            {/if}
        </div>
        {#if timeFilter === "day"}
            <p class="activity-context">{statusExplanation}</p>
            {#if chartData.length > 0}
                <div class="chart-legend">
                    <span><i class="legend-swatch current-swatch"></i>{t("diagnostics.current24Hours")}</span>
                    <span>
                        {#if hasComparison}<i class="legend-swatch previous-swatch"></i>{/if}
                        {t(hasComparison ? "diagnostics.previousWeek24Hours" : "diagnostics.previousWeekUnavailable")}
                    </span>
                </div>
            {/if}
        {/if}

        <div class="custom-chart-container">
            {#if chartData && chartData.length > 0}
                <div class="chart-bars" class:with-comparison={hasComparison}>
                    {#each chartData as value, i (`${timeFilter}-${i}`)}
                        <!-- svelte-ignore a11y-no-static-element-interactions -->
                        <div
                            class="bar-wrapper"
                            role="img"
                            aria-label={hasComparison
                                ? t("diagnostics.hourlyComparison", { time: chartLabels[i], current: value, previous: comparisonData[i] })
                                : `${chartLabels[i]}: ${t("diagnostics.incidentsCount", { count: value })}`}
                            on:mouseenter={() => (hoveredIndex = i)}
                            on:mouseleave={() => (hoveredIndex = null)}
                        >
                            <div class="bar-container">
                                {#if hasComparison}
                                    <div
                                        class="comparison-bar"
                                        class:empty={comparisonData[i] === 0}
                                        style="height: {(comparisonData[i] / yMax) * 100}%"
                                    ></div>
                                {/if}
                                <div
                                    class="bar"
                                    class:spike={timeFilter === "day" && activityStatus === "highActivity" && i === chartData.length - 1}
                                    style="height: {(value / yMax) * 100}%"
                                >
                                    {#if timeFilter === "day" && activityStatus === "highActivity" && i === chartData.length - 1}
                                        <div class="spike-glow"></div>
                                        <div class="spike-halo"></div>
                                    {/if}
                                    {#if hoveredIndex === i}
                                        <div
                                            class="chart-tooltip"
                                            transition:slide={{ duration: 150 }}
                                        >
                                            <div class="tooltip-title">
                                                {chartLabels[i]}
                                            </div>
                                            <div class="tooltip-value">
                                                {#if hasComparison}{t("diagnostics.current24Hours")}: {/if}
                                                {t("diagnostics.incidentsCount", { count: value })}
                                            </div>
                                            {#if hasComparison}
                                                <div class="tooltip-value">
                                                    {t("diagnostics.previousWeek24Hours")}: {t("diagnostics.incidentsCount", { count: comparisonData[i] })}
                                                </div>
                                            {/if}
                                        </div>
                                    {/if}
                                </div>
                            </div>
                            <!-- X-axis labels (render a subset depending on timeFilter) -->
                            <div
                                class="x-label-container"
                                class:mobile-hide-label={i !== chartLabels.length - 1 && ((timeFilter === "day" && i % 6 !== 0) || (timeFilter === "year" && i % 3 !== 0))}
                            >
                                {#if timeFilter === "day"}
                                    {#if i % 3 === 0 || i === chartLabels.length - 1}
                                        <span class="x-label">{chartLabels[i]}</span>
                                    {/if}
                                {:else if timeFilter === "week"}
                                    <span class="x-label"
                                        >{chartLabels[i].split(" ")[0]}</span
                                    >
                                {:else if timeFilter === "month"}
                                    {#if i % 5 === 0 || i === chartLabels.length - 1}
                                        <span class="x-label"
                                            >{chartLabels[i].split(
                                                " ",
                                            )[1]}</span
                                        >
                                    {/if}
                                {:else}
                                    <span class="x-label">{chartLabels[i]}</span
                                    >
                                {/if}
                            </div>
                        </div>
                    {/each}
                </div>
            {:else}
                <div class="no-data-msg">{t("diagnostics.noActivityData")}</div>
            {/if}
        </div>
    </div>

    <!-- Breakdowns -->
    <div class="incident-breakdown-grid">
        <div class="breakdown-card">
            <div class="breakdown-header">
                <div class="breakdown-title-section">
                    <span class="breakdown-icon"><BarChart3 size={18} /></span>
                    <span class="breakdown-title">{t("diagnostics.byType")}</span>
                </div>
                {#if selectedTypes.size > 0}
                    <button
                        class="reset-button"
                        on:click={resetTypeFilters}
                        title={t("actions.resetTypeFilters")}
                    >
                        <X size={14} />
                    </button>
                {/if}
            </div>
            <div class="breakdown-list">
                {#each typeEntries as [type, count]}
                    <button
                        class="breakdown-item"
                        class:selected={selectedTypes.has(type)}
                        on:click={() => filterByType(type)}
                    >
                        <span class="breakdown-icon">
                            <IncidentIcon {type} />
                        </span>
                        <span
                            class="breakdown-count-bar"
                            style="width: {(count / maxTypeCount) * 100}%"
                        ></span>
                        <div class="breakdown-text">
                            <span class="breakdown-name">{type}</span>
                            <span class="breakdown-count">{count}</span>
                        </div>
                    </button>
                {/each}
            </div>
        </div>
        <div class="breakdown-card">
            <div class="breakdown-header">
                <div class="breakdown-title-section">
                    <span class="breakdown-icon"><MapPin size={18} /></span>
                    <span class="breakdown-title">{t("diagnostics.topLocations")}</span>
                </div>
                {#if selectedLocations.size > 0}
                    <button
                        class="reset-button"
                        on:click={resetLocationFilters}
                        title={t("actions.resetLocationFilters")}
                    >
                        <X size={14} />
                    </button>
                {/if}
            </div>
            <div class="breakdown-list">
                {#each locationEntries as [location, count]}
                    <button
                        class="breakdown-item"
                        class:selected={selectedLocations.has(location)}
                        on:click={() => filterByLocation(location)}
                    >
                        <div
                            class="breakdown-count-bar"
                            style="width: {(count / maxLocationCount) * 100}%"
                        ></div>
                        <div class="breakdown-text">
                            <span class="breakdown-name">{location}</span>
                            <span class="breakdown-count">{count}</span>
                        </div>
                    </button>
                {/each}
            </div>
        </div>
    </div>
</div>

<style>
    /* Stats Panel Styles - OSINT Redesign */
    .event-counters {
        display: flex;
        flex-direction: column;
        gap: 0.8rem;
        padding: 0.9rem;
        color: var(--text-main);
    }

    .top-row {
        display: flex;
        gap: 0.8rem;
        align-items: stretch;
    }

    .stats-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.55rem;
        flex: 1;
    }

    .stat-card {
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        border-radius: 15px;
        corner-shape: squircle;
        text-align: left;
        padding: 0.6rem 0.7rem;
        display: grid;
        grid-template-columns: 28px minmax(0, 1fr);
        grid-template-rows: auto auto;
        column-gap: 0.55rem;
        align-content: center;
        align-items: center;
        min-height: 56px;
        transition: transform .3s var(--ease-out), border-color .2s, background .2s;
    }

    .stat-card:hover {
        border-color: color-mix(in srgb, var(--accent-primary) 35%, var(--border-color));
        background: var(--primary-lightest);
        transform: translateY(-2px);
    }

    .stat-icon {
        grid-row: 1 / 3;
        color: var(--accent-primary);
        filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
    }

    .stat-icon :global(svg) {
        width: 20px;
        height: 20px;
    }

    .stat-value {
        font-size: 1.45rem;
        font-weight: 760;
        letter-spacing: -.04em;
        line-height: 1;
        color: var(--text-main);
    }

    .stat-label {
        font-size: 0.75rem;
        font-weight: 500;
        opacity: 0.7;
        letter-spacing: -0.01em;
        line-height: 1.1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .time-period-section {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 0.55rem 0.65rem;
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        border-radius: 15px;
        corner-shape: squircle;
        min-width: 270px;
        gap: 0.35rem;
    }

    .section-label {
        font-size: 0.72rem;
        font-weight: 600;
        opacity: 0.8;
        letter-spacing: -0.01em;
    }

    .time-buttons {
        display: flex;
        gap: 0.25rem;
        background: var(--bg-surface-elevated);
        padding: 0.2rem;
        border-radius: 11px;
        corner-shape: squircle;
        border: 1px solid var(--border-color);
    }

    .time-button {
        padding: 0.35rem 0.65rem;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        corner-shape: squircle;
        color: var(--text-muted);
        font-size: 0.75rem;
        font-weight: 650;
        cursor: pointer;
        transition: all 0.15s ease;
    }

    :global(body.dark-mode) .time-button {
        color: rgba(255, 255, 255, 0.7);
    }

    .time-button:hover {
        color: var(--text-main);
        border-color: rgba(51, 102, 255, 0.3);
        background: rgba(51, 102, 255, 0.05);
    }

    :global(body.dark-mode) .time-button:hover {
        color: #fff;
        border-color: rgba(51, 102, 255, 0.3);
        background: rgba(51, 102, 255, 0.05);
    }

    .time-button.active {
        background: var(--primary-lightest);
        color: var(--accent-primary);
        border-color: color-mix(in srgb, var(--accent-primary) 38%, var(--border-color));
    }

    .activity-chart-section {
        padding: 0.75rem 0.9rem;
        background: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        corner-shape: squircle;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .activity-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.5rem;
        border-bottom: 1px solid var(--border-color);
        padding-bottom: 0.4rem;
    }

    .section-title {
        font-size: 0.95rem;
        font-weight: 720;
        color: var(--text-main);
    }

    .status-indicator {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        padding: 0.25rem 0.5rem;
        border-radius: 999px;
    }

    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 5px currentColor;
    }

    .status-text {
        font-size: 0.68rem;
        font-weight: bold;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    .activity-context {
        margin: 0.4rem 0 0.6rem;
        color: var(--text-muted);
        font-size: 0.72rem;
        line-height: 1.5;
    }

    .custom-chart-container {
        position: relative;
        width: 100%;
        height: 105px;
        margin-top: 2px;
        margin-bottom: 22px;
        display: flex;
        align-items: flex-end;
    }

    .chart-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 0.25rem 0.75rem;
        color: var(--text-muted);
        font-size: 0.65rem;
        line-height: 1.3;
    }

    .chart-legend > span {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
    }

    .legend-swatch {
        width: 9px;
        height: 9px;
        border-radius: 2px;
        flex-shrink: 0;
    }

    .current-swatch {
        background: var(--accent-primary);
    }

    .previous-swatch,
    .comparison-bar {
        background: color-mix(in srgb, var(--text-muted) 28%, transparent);
        border: 1px solid color-mix(in srgb, var(--text-muted) 65%, transparent);
    }

    .comparison-bar {
        position: absolute;
        bottom: 0;
        width: 100%;
        border-radius: 4px 4px 0 0;
        pointer-events: none;
        transition: height 0.4s var(--ease-out);
    }

    .comparison-bar.empty {
        visibility: hidden;
    }

    .with-comparison .bar {
        width: 55%;
        margin-inline: auto;
    }

    .chart-bars {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        width: 100%;
        height: 100%;
        gap: 4px;
    }

    .bar-wrapper {
        flex: 1;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        align-items: center;
        position: relative;
        cursor: pointer;
    }

    .bar-container {
        width: 100%;
        height: 100%;
        display: flex;
        align-items: flex-end;
        position: relative;
        border-bottom: 2px solid rgba(140, 155, 186, 0.3);
    }

    .bar-wrapper:hover {
        z-index: 10;
    }

    .bar {
        width: 100%;
        background-color: var(--accent-primary);
        border-radius: 6px 6px 2px 2px;
        corner-shape: squircle;
        transition:
            height 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275),
            background-color 0.3s;
        position: relative;
        min-height: 2px;
    }

    .bar:hover {
        filter: brightness(1.2);
    }

    /* Spike Red Glow Elements */
    .bar.spike {
        background: linear-gradient(
            180deg,
            #ef4444 0%,
            rgba(239, 68, 68, 0.4) 100%
        );
        background-color: #ef4444; /* fallback */
        box-shadow:
            0 -4px 12px rgba(239, 68, 68, 0.16),
            0 0 7px rgba(239, 68, 68, 0.12);
        z-index: 2;
    }

    .spike-glow {
        position: absolute;
        top: -7px;
        left: -3px;
        right: -3px;
        bottom: 0;
        background: linear-gradient(
            180deg,
            rgba(239, 68, 68, 0.3) 0%,
            rgba(239, 68, 68, 0.08) 48%,
            transparent 82%
        );
        border-radius: 10px 10px 4px 4px;
        corner-shape: squircle;
        filter: blur(7px);
        pointer-events: none;
        animation: glowPulse 2.8s ease-in-out infinite alternate;
    }

    .spike-halo {
        position: absolute;
        top: -19px;
        left: -85%;
        right: -85%;
        height: 34px;
        background: radial-gradient(
            ellipse at center,
            rgba(239, 68, 68, 0.16) 0%,
            rgba(239, 68, 68, 0.05) 42%,
            transparent 72%
        );
        filter: blur(5px);
        pointer-events: none;
        animation: haloPulse 2.8s ease-in-out infinite alternate;
    }

    @keyframes glowPulse {
        0% {
            opacity: 0.32;
        }
        100% {
            opacity: 0.58;
        }
    }

    @keyframes haloPulse {
        0% {
            transform: scale(0.94);
            opacity: 0.28;
        }
        100% {
            transform: scale(1.04);
            opacity: 0.48;
        }
    }

    .x-label-container {
        height: 20px;
        margin-top: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        position: absolute;
        bottom: -21px;
    }

    .x-label {
        font-size: 0.6rem;
        color: rgba(140, 155, 186, 0.8);
        font-family: var(--font-mono);
        white-space: nowrap;
        position: absolute;
    }

    .chart-tooltip {
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        margin-bottom: 8px;
        background: var(--bg-surface-elevated);
        border: 1px solid rgba(51, 102, 255, 0.3);
        padding: 6px 10px;
        border-radius: 12px;
        corner-shape: squircle;
        z-index: 10;
        pointer-events: none;
        white-space: nowrap;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    .tooltip-title {
        font-family: var(--font-mono);
        font-size: 0.7rem;
        color: var(--accent-primary);
        margin-bottom: 2px;
    }

    .tooltip-value {
        font-family: var(--font-mono);
        font-size: 0.8rem;
        color: var(--text-main);
        font-weight: bold;
    }

    .no-data-msg {
        width: 100%;
        text-align: center;
        color: var(--text-muted);
        font-size: 0.9rem;
        font-style: italic;
        padding: 2rem 0;
    }

    .incident-breakdown-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 0.65rem;
    }

    .breakdown-card {
        background: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        corner-shape: squircle;
        padding: 0.7rem;
        min-width: 0;
    }

    .breakdown-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.45rem;
        margin-bottom: 0.45rem;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid var(--border-color);
    }

    .breakdown-title-section {
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }

    .reset-button {
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        color: var(--text-muted);
        border-radius: 8px;
        corner-shape: squircle;
        padding: 5px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease;
    }

    .reset-button:hover {
        background: var(--hover-bg);
        color: var(--text-main);
        border-color: var(--accent-primary);
    }

    .breakdown-icon {
        font-size: 1rem;
        z-index: 2;
        width: 20px;
        height: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .breakdown-title {
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: -0.01em;
    }

    .breakdown-list {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        max-height: 184px;
        overflow-y: auto;
        padding-right: 0.25rem;
        scrollbar-width: none; /* Firefox */
    }

    .breakdown-list::-webkit-scrollbar {
        display: none; /* Chrome, Safari, Opera */
    }

    .breakdown-item {
        display: flex;
        align-items: center;
        position: relative;
        padding: 0.4rem 0.55rem;
        background: var(--hover-bg);
        border: none;
        border-radius: 10px;
        corner-shape: squircle;
        cursor: pointer;
        transition: all 0.2s ease;
        min-height: 34px;
        overflow: hidden;
        color: var(--text-color);
        text-align: left;
        gap: 0.5rem;
    }

    :global(body.dark-mode) .breakdown-item {
        background: rgba(255, 255, 255, 0.04);
        color: white;
    }

    .breakdown-item:hover {
        background: var(--hover-bg);
        transform: translateX(2px);
    }

    .breakdown-item.selected {
        background: var(--primary-lightest);
        box-shadow: inset 0 0 0 2px var(--primary-color);
    }

    :global(body.dark-mode) .breakdown-item.selected {
        background: rgba(66, 153, 225, 0.2);
        box-shadow: inset 0 0 0 2px var(--primary-light);
    }

    :global(body.dark-mode) .breakdown-item:hover {
        background: rgba(255, 255, 255, 0.1);
    }

    .breakdown-count-bar {
        position: absolute;
        left: 0;
        bottom: 0;
        height: 3px;
        background: var(--accent-primary);
        border-radius: 0 999px 999px 0;
        z-index: 0;
        transition: width 0.5s ease;
    }

    :global(body.dark-mode) .breakdown-count-bar {
        background: var(--accent-primary);
    }

    .breakdown-text {
        display: flex;
        flex: 1;
        align-items: center;
        justify-content: space-between;
        z-index: 2;
        min-width: 0; /* Enable truncation in flex child */
    }

    .breakdown-name {
        font-size: 0.82rem;
        font-weight: 500;
        color: var(--text-darker);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-right: 0.5rem;
    }

    .breakdown-count {
        font-weight: 600;
        color: var(--text-muted);
        background: rgba(0, 0, 0, 0.05); /* subtle pill background */
        padding: 0.08rem 0.4rem;
        border-radius: 999px;
        font-size: 0.72rem;
        z-index: 2;
    }

    :global(body.dark-mode) .breakdown-count {
        background: rgba(255, 255, 255, 0.15);
    }

    @media (min-width: 1120px) {
        .event-counters {
            display: grid;
            grid-template-columns: minmax(0, 1.45fr) minmax(520px, 1fr);
            grid-template-areas:
                "summary summary"
                "activity breakdown";
            align-items: stretch;
        }

        .top-row {
            grid-area: summary;
        }

        .activity-chart-section {
            grid-area: activity;
        }

        .incident-breakdown-grid {
            grid-area: breakdown;
        }
    }

    @media (max-width: 768px) {
        .event-counters {
            padding: 0.65rem;
            gap: 0.6rem;
        }

        .top-row {
            flex-direction: column;
            gap: 0.4rem;
        }

        .stats-grid {
            gap: 0.35rem;
        }

        .stat-card {
            grid-template-columns: minmax(0, 1fr);
            justify-items: center;
            gap: 0.2rem;
            padding: 0.5rem 0.2rem;
            min-height: 54px;
            border-radius: 11px;
            text-align: center;
        }

        .stat-icon {
            display: none;
        }

        .stat-value {
            font-size: clamp(1rem, 4.5vw, 1.3rem);
            overflow-wrap: anywhere;
        }

        .stat-label {
            font-size: 0.68rem;
            max-width: 100%;
        }

        .time-period-section {
            min-width: 0;
            padding: 0;
            border: 0;
            background: transparent;
        }

        /* Keep the group label available to assistive technology. */
        .section-label {
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip-path: inset(50%);
            white-space: nowrap;
        }

        .time-buttons {
            width: 100%;
            gap: 0.2rem;
        }

        .time-button {
            flex: 1 1 0;
            min-width: 0;
            min-height: 44px;
            padding: 0.25rem;
            font-size: 0.75rem;
        }

        .activity-chart-section {
            padding: 0.6rem;
            gap: 0.35rem;
            border-radius: 12px;
        }

        .activity-header {
            gap: 0.35rem;
            padding-bottom: 0;
            border: 0;
        }

        .section-title {
            font-size: 0.85rem;
        }

        .status-indicator {
            gap: 0.25rem;
            padding: 0.2rem 0.35rem;
        }

        .status-text {
            font-size: 0.6rem;
            letter-spacing: 0.01em;
        }

        .activity-context {
            margin: 0;
            font-size: 0.7rem;
            line-height: 1.4;
        }

        .custom-chart-container {
            height: 72px;
            margin-bottom: 20px;
        }

        .chart-bars {
            gap: 3px;
        }

        .mobile-hide-label {
            visibility: hidden;
        }

        .incident-breakdown-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.5rem;
        }

        .breakdown-card {
            padding: 0.5rem;
            border-radius: 12px;
        }

        .breakdown-header {
            min-height: 28px;
            gap: 0.2rem;
            padding-bottom: 0.25rem;
            margin-bottom: 0.3rem;
        }

        .breakdown-title-section {
            gap: 0.25rem;
            min-width: 0;
        }

        .breakdown-title {
            font-size: 0.75rem;
            line-height: 1.2;
        }

        .breakdown-icon {
            flex-shrink: 0;
            width: 16px;
            height: 16px;
        }

        .breakdown-list {
            max-height: 184px;
            gap: 0.25rem;
            padding-right: 0;
            scrollbar-width: thin;
        }

        .breakdown-list::-webkit-scrollbar {
            display: block;
            width: 3px;
        }

        .breakdown-item {
            flex-shrink: 0;
            min-height: 44px;
            padding: 0.35rem 0.4rem;
        }

        .breakdown-item > .breakdown-icon {
            display: none;
        }

        .breakdown-name {
            font-size: 0.72rem;
            line-height: 1.25;
            white-space: normal;
            overflow-wrap: anywhere;
            margin-right: 0.3rem;
        }

        .breakdown-count {
            flex-shrink: 0;
            padding: 0.08rem 0.3rem;
            font-size: 0.68rem;
        }

        .reset-button {
            flex-shrink: 0;
            min-width: 28px;
            min-height: 28px;
        }
    }
</style>
