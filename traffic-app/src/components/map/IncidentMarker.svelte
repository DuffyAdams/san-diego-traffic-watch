<script>
    import { onMount } from "svelte";
    import { fade, slide } from "../../utils/motion.js";
    import IncidentIcon from "../shared/IncidentIcon.svelte";
    import { activeMarkerId, mapPanTo } from "../../stores/appStore.js";
    import { t } from "../../utils/i18n.js";

    export let incident;

    let isHovered = false;
    $: isClicked = $activeMarkerId === incident.id;
    let markerEl;
    let showBelow = false;

    function onEnter() {
        isHovered = true;

        if (markerEl) {
            const rect = markerEl.getBoundingClientRect();
            // Estimate max height of hover card + buffer
            if (rect.top < 320) {
                showBelow = true;
            } else {
                showBelow = false;
            }
        }

        // Walk up to the MapLibre marker wrapper and raise it above all others
        const mlMarker = markerEl?.closest(".maplibregl-marker");
        if (mlMarker && !$activeMarkerId) mlMarker.style.zIndex = "9999";
    }

    function onLeave() {
        isHovered = false;
        const mlMarker = markerEl?.closest(".maplibregl-marker");
        if (mlMarker && !isClicked) mlMarker.style.zIndex = "";
    }

    function toggleClick(e) {
        e.stopPropagation();
        if ($activeMarkerId === incident.id) {
            $activeMarkerId = null;
            isHovered = false;
        } else {
            if (incident.latitude != null && incident.longitude != null) {
                mapPanTo.set({
                    id: incident.id,
                    latitude: incident.latitude,
                    longitude: incident.longitude,
                    preserveZoom: true,
                });
            }
            $activeMarkerId = incident.id;
        }
    }

    // Reactively update z-index when state changes
    $: {
        if (markerEl) {
            const mlMarker = markerEl.closest(".maplibregl-marker");
            if (mlMarker) {
                mlMarker.style.zIndex =
                    (isHovered && !$activeMarkerId) || isClicked ? "9999" : "";
            }
        }
    }

    // Color based on source and active status
    $: sourceColor =
        incident.source === "SDFD"
            ? "#ff3333"
            : incident.source === "SDPD"
              ? "#3366ff"
              : incident.source === "SDSO"
                ? "#00ccff"
                : "#ffaa33"; // Default for CHP/Traffic

    // Dim the color if inactive
    $: iconColor = incident.active ? sourceColor : "#666666";

    // 4-step brightness (opacity) based on event age
    $: ageMs = Date.now() - new Date(incident.timestamp).getTime();
    $: ageMinutes = ageMs / (1000 * 60);

    $: activeOpacity =
        ageMinutes < 30
            ? 1
            : ageMinutes < 60
              ? 0.8
              : ageMinutes < 120
                ? 0.6
                : 0.4;

    $: markerOpacity =
        (isHovered && !$activeMarkerId) || isClicked
            ? 1
            : incident.active
              ? activeOpacity
              : 0.65;

    const severityConfig = {
        1: { label: "MINOR", color: "#64748b" },
        2: { label: "LOW", color: "#06b6d4" },
        3: { label: "MODERATE", color: "#eab308" },
        4: { label: "HIGH", color: "#f97316" },
        5: { label: "CRITICAL", color: "#ef4444" },
    };
    $: sevInfo = incident.severity ? severityConfig[incident.severity] : null;
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_mouse_events_have_key_events -->
<div
    class="marker-container"
    bind:this={markerEl}
    on:mouseenter={onEnter}
    on:mouseleave={onLeave}
    on:click={toggleClick}
    style="opacity: {markerOpacity};"
>
    <!-- Pulsating Ring for Active Incidents (recent < 15min) -->
    {#if incident.active && ageMinutes <= 15}
        <div
            class="pulse-ring"
            style="background-color: {sourceColor}40;"
        ></div>
    {/if}

    <!-- Icon Container -->
    <div
        class="icon-wrapper"
        class:inactive={!incident.active}
        class:is-clicked={isClicked}
        style="--icon-color: {iconColor}; --glow-color: {sourceColor};"
    >
        <IncidentIcon
            type={incident.type}
            size={14}
            fill={incident.active ? iconColor : "none"}
            color={incident.active ? "#fff" : iconColor}
        />
    </div>

    <!-- Hover Preview Card -->
    {#if (isHovered && !$activeMarkerId) || isClicked}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
        class="hover-card"
        class:show-below={showBelow}
        class:is-clicked={isClicked}
        transition:slide={{ duration: 200 }}
        style="border-color: {sourceColor}4d;"
        on:click={toggleClick}
    >
            <div
                class="card-header"
                style="border-bottom-color: {sourceColor}33;"
            >
                <span class="type" style="color: {sourceColor};"
                    >{incident.type || t("fallback.incidentType")}</span
                >
                <div style="display: flex; align-items: center; gap: 8px;">
                    {#if sevInfo}
                        <span
                            class="sev-pill"
                            style="color: {sevInfo.color}; border-color: {sevInfo.color};"
                            >{incident.severity}</span
                        >
                    {/if}
                    <span class="time">{incident.time}</span>
                    {#if isClicked}
                        <!-- svelte-ignore a11y_consider_explicit_label -->
                        <button
                            class="close-btn"
                            on:click={(e) => {
                                e.stopPropagation();
                                $activeMarkerId = null;
                                isHovered = false;
                            }}>×</button
                        >
                    {/if}
                </div>
            </div>

            <div class="card-body">
                <div class="location">
                    <span class="label">LOC</span>
                    <span class="value text-truncate">{incident.location}</span>
                </div>
                {#if incident.neighborhood && incident.neighborhood !== "N/A" && incident.neighborhood !== ""}
                    <div class="neighborhood">
                        <span class="label">AREA</span>
                        <span class="value">{incident.neighborhood}</span>
                    </div>
                {/if}
                {#if incident.description && incident.description !== t("fallback.descriptionUnavailable")}
                    <div
                        class="description"
                        style="border-top-color: {sourceColor}26;"
                    >
                        <span class="label">INFO</span>
                        <span class="value desc-text"
                            >{incident.description
                                .split("Neighborhood:")[0]
                                .replace(
                                    /Provide a factual.*?Keep the summary under 200 characters\. Add related emojis\. Summarize this traffic incident in one fluent sentence\.\s*/i,
                                    "",
                                )
                                .trim()}</span
                        >
                    </div>
                {/if}
                {#if incident.details && incident.details.length > 0}
                    <div
                        class="details"
                        style="border-top-color: {sourceColor}1a;"
                    >
                        {#each incident.details as detail}
                            <div class="detail-line">{detail}</div>
                        {/each}
                    </div>
                {/if}
            </div>
            <div
                class="arrow"
                class:arrow-up={showBelow}
                class:arrow-down={!showBelow}
                style="filter: drop-shadow(0 {showBelow
                    ? '-1px'
                    : '1px'} 0 {sourceColor}4d);"
            ></div>
        </div>
    {/if}
</div>

<style>
    .marker-container {
        position: relative;
        cursor: pointer;
        /* Expand the container itself to act as the native hit area */
        width: 48px;
        height: 48px;
        border-radius: 50%;
        background-color: rgba(
            0,
            0,
            0,
            0.01
        ); /* Barely painted so iOS registers touch */
        -webkit-tap-highlight-color: transparent;
        z-index: 10;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: opacity 0.2s ease;
    }

    @media (pointer: coarse) {
        .marker-container {
            width: 64px; /* Huge reliable touch area on mobile */
            height: 64px;
        }
    }

    .marker-container:hover {
        z-index: 1000;
    }

    .marker-container:hover .pulse-ring {
        display: none;
    }

    .marker-container:hover .icon-wrapper,
    .icon-wrapper.is-clicked {
        box-shadow: 0 0 16px var(--glow-color);
        transform: scale(1.1);
        border-color: #fff;
    }

    .icon-wrapper {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 20px;
        height: 20px;
        background-color: rgba(10, 15, 20, 0.9);
        border-radius: 50%;
        position: relative;
        z-index: 2;
        box-shadow: 0 0 8px var(--icon-color);
        border: 1px solid var(--icon-color);
        transition: all 0.2s ease;
        padding: 2px;
    }

    .icon-wrapper.inactive {
        width: 16px;
        height: 16px;
        box-shadow: none;
        border: 1px solid rgba(150, 150, 150, 0.4);
        opacity: 0.85;
        background-color: rgba(20, 20, 20, 0.8);
    }

    .marker-container:hover .icon-wrapper.inactive,
    .icon-wrapper.inactive.is-clicked {
        opacity: 1;
        box-shadow: 0 0 8px rgba(200, 200, 200, 0.4);
        transform: scale(1.2);
        border-color: #fff;
    }

    .pulse-ring {
        position: absolute;
        top: 50%;
        left: 50%;
        margin-top: -12px;
        margin-left: -12px;
        width: 24px;
        height: 24px;
        background-color: rgba(255, 51, 51, 0.4);
        border-radius: 50%;
        z-index: 1;
        animation: pulse 2s infinite cubic-bezier(0.4, 0, 0.2, 1);
        pointer-events: none;
    }

    @keyframes pulse {
        0% {
            transform: scale(0.5);
            opacity: 1;
        }
        100% {
            transform: scale(2.5);
            opacity: 0;
        }
    }

    /* Hover Card */
    .hover-card {
        position: absolute;
        bottom: 50%;
        margin-bottom: 12px; /* Position above the icon center */
        left: 50%;
        transform-origin: bottom center;
        transform: translateX(-50%);
        width: 280px;
        max-height: 300px;
        overflow-y: auto;
        background: #080c12;
        border: 1px solid rgba(136, 170, 255, 0.3);
        border-radius: 6px;
        corner-shape: squircle;
        padding: 10px;
        box-shadow:
            0 4px 12px rgba(0, 0, 0, 0.5),
            0 0 0 1px rgba(136, 170, 255, 0.1);
        pointer-events: none; /* Let mouse remain on dot */
        color: #e0e0e0;
        font-family: "Share Tech Mono", monospace, ui-monospace, SFMono-Regular;
        z-index: 9999;
    }

    .hover-card.is-clicked {
        pointer-events: auto;
    }

    .hover-card.show-below {
        bottom: auto;
        top: 24px; /* Position below the dot */
        transform-origin: top center;
    }

    .arrow {
        position: absolute;
        left: 50%;
        transform: translateX(-50%);
        width: 0;
        height: 0;
        border-left: 6px solid transparent;
        border-right: 6px solid transparent;
    }

    .arrow-down {
        bottom: -6px;
        border-top: 6px solid rgba(8, 12, 18, 0.95);
        filter: drop-shadow(0 1px 0 rgba(136, 170, 255, 0.3));
    }

    .arrow-up {
        top: -6px;
        border-bottom: 6px solid rgba(8, 12, 18, 0.95);
        filter: drop-shadow(0 -1px 0 rgba(136, 170, 255, 0.3));
    }

    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid rgba(136, 170, 255, 0.2);
        padding-bottom: 6px;
        margin-bottom: 6px;
        font-size: 0.75rem;
    }

    .type {
        color: #ff5555;
        font-weight: bold;
        text-transform: uppercase;
        max-width: 140px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .time {
        color: #88bbaa;
        font-size: 0.7rem;
    }

    .card-body {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 0.75rem;
    }

    .location {
        display: flex;
        gap: 6px;
    }

    .neighborhood {
        display: flex;
        gap: 6px;
    }

    .label {
        color: #557799;
        font-weight: bold;
        min-width: 32px;
    }

    .value {
        color: #cccccc;
    }

    .text-truncate {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex: 1;
    }

    .description {
        display: flex;
        gap: 6px;
        margin-top: 4px;
        padding-top: 4px;
        border-top: 1px solid rgba(136, 170, 255, 0.15);
    }

    .desc-text {
        white-space: normal;
        word-wrap: break-word;
        line-height: 1.3;
        color: #aabbcc;
        flex: 1;
    }

    .details {
        margin-top: 4px;
        padding-top: 4px;
        border-top: 1px solid rgba(136, 170, 255, 0.1);
        font-size: 0.7rem;
    }

    .detail-line {
        color: #8899aa;
        padding: 1px 0;
        white-space: normal;
        word-wrap: break-word;
    }

    .close-btn {
        background: rgba(255, 51, 51, 0.1);
        border: 1px solid rgba(255, 51, 51, 0.3);
        color: #ff5555;
        border-radius: 4px;
        corner-shape: squircle;
        width: 20px;
        height: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        line-height: 1;
        cursor: pointer;
        padding: 0;
        transition: all 0.2s;
    }

    .close-btn:hover {
        background: rgba(255, 51, 51, 0.3);
        color: #fff;
    }

    .sev-pill {
        font-size: 0.6rem;
        font-weight: 900;
        border: 1px solid;
        border-radius: 4px;
        corner-shape: squircle;
        padding: 1px 4px;
        line-height: 1;
        text-align: center;
        min-width: 14px;
    }
</style>
