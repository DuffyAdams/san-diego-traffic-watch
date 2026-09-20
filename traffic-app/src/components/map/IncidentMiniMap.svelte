<script context="module">
    import "maplibre-gl/dist/maplibre-gl.css";
    import {
        loadMapLibraries as loadSharedMapLibraries,
        PMTILES_URL,
    } from "../../utils/mapRuntime.js";

    // Keep comfortably below common mobile WebGL context limits. The full map,
    // charts, and browser UI may all need GPU resources at the same time.
    const MAX_ACTIVE_MINI_MAPS = 4;
    let activeMiniMaps = [];
    let maplibregl = null;

    async function loadMapLibraries() {
        const libraries = await loadSharedMapLibraries();
        maplibregl = libraries.maplibregl;
        return libraries;
    }

    function claimMiniMapSlot(instance) {
        activeMiniMaps = activeMiniMaps.filter((item) => item !== instance);
        activeMiniMaps.push(instance);

        while (activeMiniMaps.length > MAX_ACTIVE_MINI_MAPS) {
            const evictionIndex = activeMiniMaps.findIndex(
                (item) => item !== instance && !item.isNearViewport(),
            );

            if (evictionIndex === -1) break;
            const [evicted] = activeMiniMaps.splice(evictionIndex, 1);
            evicted?.deactivate();
        }
    }

    function releaseMiniMapSlot(instance) {
        activeMiniMaps = activeMiniMaps.filter((item) => item !== instance);
    }
</script>

<script>
    import { onMount, onDestroy, tick } from "svelte";
    import IncidentIcon from "../shared/IncidentIcon.svelte";
    import { pageVisible } from "../../stores/pageActivity.js";
    import { t } from "../../utils/i18n.js";
    import { shareableMap } from "../../utils/shareImage.js";

    export let latitude = null;
    export let longitude = null;
    export let type = "Incident";
    export let active = false;
    export let deferActivation = false;

    const MINI_MAP_ZOOM = 14.35;
    const MINI_MAP_PITCH = 58;
    const MINI_MAP_BEARING = -22;
    const ACTIVATION_DELAY_MS = 250;
    const DEACTIVATION_DELAY_MS = 700;
    let shell;
    let mapContainer;
    let map;
    let observer;
    let resizeObserver;
    let resizeFrame = 0;
    let activationTimer = 0;
    let deactivationTimer = 0;
    let readyFallbackTimer = 0;
    let isNearViewport = false;
    let canRenderMap = false;
    let mapReady = false;
    let hasRenderedOnce = false;
    let mapUnavailable = false;
    let isDestroyed = false;
    let initRequestId = 0;
    let lastCoordinateKey = "";

    const incidentColors = {
        "Traffic Hazard": "#fbbf24",
        "Traffic Collision": "#ef4444",
        "Car Fire": "#f97316",
        "Report of Fire": "#f97316",
        Fatality: "#991b1b",
        "Hit and Run No Injuries": "#dc2626",
        "Road Closure": "#374151",
        Construction: "#f59e0b",
        "Debris From Vehicle": "#9ca3af",
        "Debris from Vehicle": "#9ca3af",
        "Live or Dead Animal": "#a78bfa",
        "Animal Hazard": "#a78bfa",
        "Defective Traffic Signals": "#eab308",
        JUMPER: "#8b5cf6",
        SPINOUT: "#06b6d4",
        "Wrong Way Driver": "#ec4899",
        "SIG Alert": "#dc2626",
        "Aircraft Emergency": "#3b82f6",
        "Provide Traffic Control": "#6366f1",
        Maintenance: "#6b7280",
        "Road Conditions": "#84cc16",
        "Traffic Break": "#0ea5e9",
        "NO DETAIL ACCIDENT": "#ef4444",
        "MINOR INJURY ACCIDENT": "#ef4444",
        "SERIOUS INJURY ACCIDENT": "#dc2626",
        "MISD HIT/RUN": "#ef4444",
        "HIT AND RUN REPORT": "#ef4444",
        "HAZARDOUS CONDITION": "#fbbf24",
        "BURGLARY ALARM": "#3b82f6",
        BATTERY: "#8b5cf6",
        "PRISONER IN CUSTODY": "#374151",
        "DISTURBING PEACE": "#6366f1",
        "DISTURBING PEACE W/VIOLENCE": "#6366f1",
        "REPORT OF DEATH": "#000000",
        "MENTAL CASE": "#ec4899",
        Medical: "#ef4444",
        MEDICAL: "#ef4444",
        "Traffic Accident (L1)": "#f59e0b",
        "Traffic Accident FWY": "#f59e0b",
        "Vehicle Fire": "#f97316",
    };

    $: markerColor = incidentColors[type] || "#fbbf24";

    const miniMapInstance = {
        deactivate() {
            cancelMapDeactivation();
            canRenderMap = false;
            destroyMap(false);
        },
        isNearViewport() {
            return isNearViewport;
        },
        isMapReady() {
            return mapReady;
        },
    };

    function canActivateMap() {
        return $pageVisible && isNearViewport && (!deferActivation || hasRenderedOnce);
    }

    function requestMapSlot() {
        if (!canActivateMap()) return;
        cancelMapDeactivation();
        mapUnavailable = false;
        claimMiniMapSlot(miniMapInstance);
        canRenderMap = true;
    }

    function scheduleMapActivation() {
        if (!canActivateMap() || canRenderMap || mapUnavailable || activationTimer) return;

        activationTimer = window.setTimeout(() => {
            activationTimer = 0;
            requestMapSlot();
        }, ACTIVATION_DELAY_MS);
    }

    function cancelMapActivation() {
        if (!activationTimer) return;
        window.clearTimeout(activationTimer);
        activationTimer = 0;
    }

    function cancelMapDeactivation() {
        if (!deactivationTimer) return;
        window.clearTimeout(deactivationTimer);
        deactivationTimer = 0;
    }

    function scheduleMapDeactivation() {
        cancelMapActivation();
        if (deactivationTimer) return;

        deactivationTimer = window.setTimeout(() => {
            deactivationTimer = 0;
            if (isDestroyed || (isNearViewport && $pageVisible)) return;
            canRenderMap = false;
            initRequestId++;
            destroyMap();
        }, DEACTIVATION_DELAY_MS);
    }

    function clearReadyFallbackTimer() {
        if (!readyFallbackTimer) return;
        window.clearTimeout(readyFallbackTimer);
        readyFallbackTimer = 0;
    }

    function markMapReady() {
        if (!map || isDestroyed) return;
        clearReadyFallbackTimer();
        mapReady = true;
        hasRenderedOnce = true;
    }

    function scheduleReadyFallback(delay = 700) {
        if (readyFallbackTimer || mapReady || !map || isDestroyed) return;

        readyFallbackTimer = window.setTimeout(() => {
            readyFallbackTimer = 0;
            markMapReady();
        }, delay);
    }

    function startResizeObserver() {
        if (resizeObserver || !("ResizeObserver" in window) || !shell) return;

        resizeObserver = new ResizeObserver(() => {
            if (!map || resizeFrame) return;
            resizeFrame = requestAnimationFrame(() => {
                resizeFrame = 0;
                if (!map) return;
                map.resize();
            });
        });

        resizeObserver.observe(shell);
        if (mapContainer) {
            resizeObserver.observe(mapContainer);
        }
    }

    function stopResizeObserver() {
        if (!resizeObserver) return;
        resizeObserver.disconnect();
        resizeObserver = null;
        if (resizeFrame) {
            cancelAnimationFrame(resizeFrame);
            resizeFrame = 0;
        }
    }

    async function createMap() {
        const requestId = ++initRequestId;
        if (
            map ||
            !canRenderMap ||
            mapUnavailable ||
            longitude == null ||
            latitude == null ||
            !mapContainer
        )
            return;

        try {
            await loadMapLibraries();
            await tick();
        } catch (error) {
            console.warn("IncidentMiniMap: failed to load map libraries", error);
            handleMapUnavailable();
            return;
        }

        if (
            isDestroyed ||
            requestId !== initRequestId ||
            map ||
            !canRenderMap ||
            mapUnavailable ||
            longitude == null ||
            latitude == null ||
            !mapContainer ||
            !document.body.contains(mapContainer)
        ) {
            return;
        }

        mapReady = false;

        try {
            map = new maplibregl.Map({
                container: mapContainer,
                style: getStyle(),
                center: [longitude, latitude],
                zoom: MINI_MAP_ZOOM,
                pitch: MINI_MAP_PITCH,
                bearing: MINI_MAP_BEARING,
                interactive: false,
                attributionControl: false,
                fadeDuration: 0,
                pixelRatio: Math.min(window.devicePixelRatio || 1, 1.25),
                maxTileCacheSize: 12,
                maxTileCacheZoomLevels: 1,
            });
        } catch (error) {
            console.warn("IncidentMiniMap: failed to create map", error);
            handleMapUnavailable();
            return;
        }

        startResizeObserver();

        map.on("error", (event) => {
            console.warn("IncidentMiniMap: map failed to load", event?.error || event);
            scheduleReadyFallback();
        });

        map.once("load", () => {
            updatePosition();
            requestAnimationFrame(() => {
                if (map) {
                    map.resize();
                    scheduleReadyFallback();
                }
            });
        });

        map.once("idle", () => {
            validateRenderedMap();
        });
    }

    function destroyMap(releaseSlot = true) {
        if (releaseSlot) {
            releaseMiniMapSlot(miniMapInstance);
        }
        stopResizeObserver();
        if (!map) return;
        clearReadyFallbackTimer();
        map.remove();
        map = null;
        mapReady = false;
    }

    function handleMapUnavailable() {
        mapUnavailable = true;
        canRenderMap = false;
        initRequestId++;
        destroyMap();
    }

    function validateRenderedMap() {
        if (!map || isDestroyed) return;

        const renderedFeatures = map.queryRenderedFeatures({
            layers: [
                "earth",
                "landuse_park",
                "water",
                "buildings",
                "road_minor",
                "road_major",
                "road_highway_casing",
                "road_highway",
            ],
        });

        if (renderedFeatures.length === 0) {
            scheduleReadyFallback(250);
            return;
        }

        markMapReady();
    }

    function getStyle() {
        return {
            version: 8,
            name: "Incident Mini Map",
            light: {
                anchor: "viewport",
                color: "#d7e3ff",
                intensity: 0.28,
                position: [1.2, 210, 35],
            },
            sources: {
                sandiego: {
                    type: "vector",
                    url: "pmtiles://" + PMTILES_URL,
                },
            },
            glyphs: "/fonts/{fontstack}/{range}.pbf",
            layers: [
                {
                    id: "background",
                    type: "background",
                    paint: { "background-color": "#08090a" },
                },
                {
                    id: "earth",
                    source: "sandiego",
                    "source-layer": "earth",
                    type: "fill",
                    paint: { "fill-color": "#101317" },
                },
                {
                    id: "landuse_park",
                    source: "sandiego",
                    "source-layer": "landuse",
                    filter: [
                        "in",
                        "kind",
                        "park",
                        "nature_reserve",
                        "garden",
                        "golf_course",
                    ],
                    type: "fill",
                    paint: { "fill-color": "#0a1a0e", "fill-opacity": 0.65 },
                },
                {
                    id: "water",
                    source: "sandiego",
                    "source-layer": "water",
                    type: "fill",
                    paint: { "fill-color": "#06111d" },
                },
                {
                    id: "buildings",
                    source: "sandiego",
                    "source-layer": "buildings",
                    type: "fill-extrusion",
                    minzoom: 13,
                    paint: {
                        "fill-extrusion-color": "#202632",
                        "fill-extrusion-height": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            13,
                            0,
                            15,
                            ["case", ["has", "height"], ["get", "height"], 10],
                        ],
                        "fill-extrusion-base": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            13,
                            0,
                            15,
                            [
                                "case",
                                ["has", "min_height"],
                                ["get", "min_height"],
                                0,
                            ],
                        ],
                        "fill-extrusion-opacity": 0.62,
                        "fill-extrusion-vertical-gradient": true,
                    },
                },
                {
                    id: "road_minor",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["in", "kind", "minor_road", "other"],
                    type: "line",
                    minzoom: 12,
                    paint: {
                        "line-color": "#262c36",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            12,
                            0.5,
                            16,
                            2,
                        ],
                    },
                },
                {
                    id: "road_major",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["in", "kind", "major_road", "medium_road"],
                    type: "line",
                    paint: {
                        "line-color": "#3d465c",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            10,
                            1,
                            16,
                            4,
                        ],
                    },
                },
                {
                    id: "road_highway_casing",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "highway"],
                    type: "line",
                    paint: {
                        "line-color": "#112f78",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            8,
                            2,
                            16,
                            8,
                        ],
                        "line-opacity": 0.45,
                    },
                },
                {
                    id: "road_highway",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "highway"],
                    type: "line",
                    paint: {
                        "line-color": "#2f66ff",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            8,
                            1,
                            16,
                            5,
                        ],
                        "line-opacity": 0.9,
                    },
                },
                {
                    id: "road_label_named",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: [
                        "all",
                        ["has", "name"],
                        ["in", "kind", "highway", "major_road", "medium_road", "minor_road"],
                    ],
                    type: "symbol",
                    minzoom: 13,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Regular"],
                        "text-size": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            13,
                            9,
                            16,
                            11,
                        ],
                        "symbol-placement": "line",
                        "symbol-spacing": 240,
                        "text-max-angle": 30,
                        "text-allow-overlap": false,
                        "text-ignore-placement": false,
                    },
                    paint: {
                        "text-color": "#aab4c7",
                        "text-halo-color": "#08090a",
                        "text-halo-width": 1.25,
                        "text-opacity": 0.86,
                    },
                },
            ],
        };
    }

    function updatePosition() {
        if (!map || longitude == null || latitude == null) return;
        const center = [longitude, latitude];
        map.jumpTo({ center });
    }

    function resetForCoordinateChange(latitude, longitude) {
        const coordinateKey = `${latitude ?? ""},${longitude ?? ""}`;
        if (coordinateKey === lastCoordinateKey) return;

        lastCoordinateKey = coordinateKey;
        mapUnavailable = false;
        mapReady = false;
        initRequestId++;
        destroyMap(false);
    }

    onMount(() => {
        isDestroyed = false;
        if (longitude == null || latitude == null) return;

        if (!("IntersectionObserver" in window)) {
            isNearViewport = true;
            requestMapSlot();
            return;
        }

        observer = new IntersectionObserver(
            ([entry]) => {
                isNearViewport = entry.isIntersecting;
                if (isNearViewport) {
                    cancelMapDeactivation();
                    scheduleMapActivation();
                } else {
                    scheduleMapDeactivation();
                }
            },
            {
                rootMargin: "180px 0px",
                threshold: 0,
            },
        );
        observer.observe(shell);
    });

    $: resetForCoordinateChange(latitude, longitude);
    $: if ($pageVisible && isNearViewport && (!deferActivation || hasRenderedOnce) && !canRenderMap && !mapUnavailable)
        scheduleMapActivation();
    $: if (!$pageVisible) scheduleMapDeactivation();
    $: if (isNearViewport && canRenderMap && mapContainer && latitude != null && longitude != null) void createMap();
    $: updatePosition();

    onDestroy(() => {
        isDestroyed = true;
        initRequestId++;
        cancelMapActivation();
        cancelMapDeactivation();
        if (observer) observer.disconnect();
        destroyMap();
    });
</script>

<div
    class="mini-map-shell"
    class:loading={!mapReady && !mapUnavailable && isNearViewport && $pageVisible}
    class:pending={!mapReady}
    bind:this={shell}
    use:shareableMap={() => mapReady ? map : null}
    style="--marker-color: {markerColor};"
>
    <div
        class:ready={mapReady}
        class="mini-map-fallback"
        aria-hidden="true"
    >
    </div>
    {#if canRenderMap}
        <div
            class:ready={mapReady}
            class="mini-map"
            bind:this={mapContainer}
        ></div>
    {/if}
    <div
        class:active={active && isNearViewport && $pageVisible}
        class="mini-incident-icon"
        title={type}
    >
        <IncidentIcon {type} />
    </div>
    {#if !mapReady}
        <div class="mini-map-status" class:visually-hidden={!mapUnavailable} role="status">
            <span>{t(mapUnavailable ? "state.mapUnavailable" : "state.loadingMap")}</span>
        </div>
    {/if}
</div>

<style>
    .mini-map-shell {
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
        background: #101317;
    }

    .mini-map-fallback,
    .mini-map {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
    }

    /* A snapshot of this renderer gives the skeleton the same streets,
       highway colors, buildings, and camera angle as the loaded maps. */
    .mini-map-fallback {
        background: #101317 url("/map-loading.jpg") center / cover no-repeat;
        filter: blur(7px) saturate(0.7);
        transform: scale(1.1);
        opacity: 0.8;
        transition: opacity 320ms ease;
        pointer-events: none;
    }

    .mini-map-fallback.ready {
        opacity: 0;
    }

    .mini-map-shell.loading::after {
        content: "";
        position: absolute;
        inset: 0;
        z-index: 1;
        pointer-events: none;
        background: linear-gradient(
            105deg,
            transparent 20%,
            rgb(176 198 230 / 7%) 48%,
            transparent 76%
        );
        animation: miniMapShimmer 2.4s ease-in-out infinite;
    }

    .mini-map {
        background: #08090a;
        opacity: 0;
        transition: opacity 320ms ease;
        z-index: 1;
    }

    .mini-map.ready {
        opacity: 1;
    }

    .mini-map-status {
        position: absolute;
        left: 50%;
        bottom: 18px;
        transform: translateX(-50%);
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 7px 11px;
        border: 1px solid rgb(148 174 205 / 12%);
        border-radius: 999px;
        background: rgb(14 21 31 / 90%);
        color: #b5c4d7;
        font-size: 11px;
        font-weight: 500;
        line-height: 1;
        letter-spacing: 0.02em;
        white-space: nowrap;
        z-index: 3;
        pointer-events: none;
    }

    .visually-hidden {
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip-path: inset(50%);
        white-space: nowrap;
        border: 0;
    }

    .pending .mini-incident-icon {
        opacity: 0;
    }

    .pending .mini-incident-icon.active::before {
        animation: none;
    }

    .mini-incident-icon {
        position: absolute;
        left: 50%;
        top: 50%;
        width: 22px;
        height: 22px;
        transform: translate(-50%, -50%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        background: var(--marker-color);
        border: 2px solid #ffffff;
        box-shadow:
            0 0 0 4px color-mix(in srgb, var(--marker-color) 20%, transparent),
            0 0 16px color-mix(in srgb, var(--marker-color) 60%, transparent);
        z-index: 2;
        transition: opacity 240ms ease;
    }

    .mini-incident-icon :global(svg) {
        width: 13px;
        height: 13px;
        stroke-width: 2.5;
    }

    .mini-incident-icon.active::before {
        content: "";
        position: absolute;
        inset: -6px;
        border: 2px solid var(--marker-color);
        border-radius: 50%;
        pointer-events: none;
        animation: miniPulse 1.8s ease-out infinite;
    }

    @keyframes miniPulse {
        from { transform: scale(.8); opacity: .55; }
        to { transform: scale(1.5); opacity: 0; }
    }

    @keyframes miniMapShimmer {
        from { transform: translateX(-100%); }
        to { transform: translateX(100%); }
    }

    @media (prefers-reduced-motion: reduce) {
        .mini-map-shell.loading::after,
        .mini-incident-icon.active::before {
            animation: none;
        }

        .mini-map,
        .mini-map.ready,
        .mini-incident-icon,
        .mini-map-fallback {
            transition: none;
        }
    }
</style>
