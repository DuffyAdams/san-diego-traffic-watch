<script>
    import { onMount, mount, tick, unmount } from "svelte";
    import "maplibre-gl/dist/maplibre-gl.css";

    import IncidentMarker from "./IncidentMarker.svelte";
    import { loadMapLibraries, PMTILES_URL } from "../../utils/mapRuntime.js";
    import { formatTimestamp, formatTime } from "../../utils/helpers.js";
    import { activeMarkerId, mapPanTo } from "../../stores/appStore.js";
    import { t } from "../../utils/i18n.js";
    import { fade, motionDuration } from "../../utils/motion.js";
    import { pageVisible } from "../../stores/pageActivity.js";

    // We no longer rely on the parent's paginated feed.
    // MapTab fetches its own complete dataset.
    export let isVisible = false;
    let allIncidents = [];
    let activeIncidents = [];

    let mapContainer;
    let map;
    let markers = {}; // Store marker references by ID
    let refreshInterval;
    let incidentsController;
    let maplibregl = null;
    let isDestroyed = false;
    let resizeObserver;
    let resizeFrame = 0;
    let mapReady = false;
    let mapLoadError = "";

    let showCHP = true;
    let showSDPD = true;
    let showSDSO = true;
    let showSDFD = true;

    const SAN_DIEGO_BOUNDS = [
        [-117.35, 32.45], // Southwest corner
        [-116.75, 33.18], // Northeast corner
    ];
    const CONSTRAINT_PADDING = {
        lng: 0.06,
        lat: 0.04,
    };
    const CONSTRAINED_BOUNDS = [
        [
            SAN_DIEGO_BOUNDS[0][0] - CONSTRAINT_PADDING.lng,
            SAN_DIEGO_BOUNDS[0][1] - CONSTRAINT_PADDING.lat,
        ],
        [
            SAN_DIEGO_BOUNDS[1][0] + CONSTRAINT_PADDING.lng,
            SAN_DIEGO_BOUNDS[1][1] + CONSTRAINT_PADDING.lat,
        ],
    ];
    const [BOUNDS_SW, BOUNDS_NE] = CONSTRAINED_BOUNDS;
    const RUBBER_BAND_RESISTANCE = 0.18;
    const MIN_ZOOM = 9.2;
    const INCIDENT_FOCUS_MIN_ZOOM = 12.5;
    const INCIDENT_FOCUS_ZOOM = 14;
    const MAP_PITCH = 48;
    const MAP_BEARING = -14;

    function getIncidentRenderKey(incident) {
        return [
            incident.incident_no ?? incident.id ?? "",
            incident.timestamp ?? "",
            incident.location ?? "",
            incident.source ?? "",
        ].join("|");
    }

    function getMarkerDataKey(incident) {
        return JSON.stringify([
            incident.latitude,
            incident.longitude,
            incident.description,
            incident.location,
            incident.neighborhood,
            incident.type,
            incident.source,
            incident.severity,
            incident.details,
        ]);
    }

    function clamp(value, min, max) {
        return Math.min(max, Math.max(min, value));
    }

    function getClampedCenter(center) {
        return new maplibregl.LngLat(
            clamp(center.lng, BOUNDS_SW[0], BOUNDS_NE[0]),
            clamp(center.lat, BOUNDS_SW[1], BOUNDS_NE[1]),
        );
    }

    function getRubberBandCenter(center) {
        let lng = center.lng;
        let lat = center.lat;
        let isOutside = false;

        if (lng < BOUNDS_SW[0]) {
            lng = BOUNDS_SW[0] + (lng - BOUNDS_SW[0]) * RUBBER_BAND_RESISTANCE;
            isOutside = true;
        } else if (lng > BOUNDS_NE[0]) {
            lng = BOUNDS_NE[0] + (lng - BOUNDS_NE[0]) * RUBBER_BAND_RESISTANCE;
            isOutside = true;
        }

        if (lat < BOUNDS_SW[1]) {
            lat = BOUNDS_SW[1] + (lat - BOUNDS_SW[1]) * RUBBER_BAND_RESISTANCE;
            isOutside = true;
        } else if (lat > BOUNDS_NE[1]) {
            lat = BOUNDS_NE[1] + (lat - BOUNDS_NE[1]) * RUBBER_BAND_RESISTANCE;
            isOutside = true;
        }

        return {
            center: new maplibregl.LngLat(lng, lat),
            isOutside,
        };
    }

    function softConstrain(lngLat, zoom) {
        const { center } = getRubberBandCenter(lngLat);
        return { center, zoom: Math.max(zoom, MIN_ZOOM) };
    }

    function getIncidentFocusZoom(preserveZoom = false) {
        if (!map) return INCIDENT_FOCUS_ZOOM;

        return preserveZoom
            ? Math.max(map.getZoom(), INCIDENT_FOCUS_MIN_ZOOM)
            : INCIDENT_FOCUS_ZOOM;
    }

    function snapBackToBounds(animated = true) {
        if (!map) return;

        const center = map.getCenter();
        const clamped = getClampedCenter(center);
        const needsSnap =
            center.lng !== clamped.lng || center.lat !== clamped.lat;

        if (!needsSnap) return;

        map.easeTo({
            center: clamped,
            duration: motionDuration(animated ? 260 : 0),
        });
    }

    function toggleFilter(source) {
        if (source === "CHP") showCHP = !showCHP;
        else if (source === "POLICE") {
            // Toggle both Police and Sheriff together based on Police's current state
            const toggledState = !showSDPD;
            showSDPD = toggledState;
            showSDSO = toggledState;
        }
        else if (source === "SDFD") showSDFD = !showSDFD;
        updateMarkers();
    }

    async function fetchAllIncidents() {
        if (incidentsController || isDestroyed || !isVisible || document.hidden || !navigator.onLine) return;
        const controller = new AbortController();
        incidentsController = controller;
        try {
            const res = await fetch("/api/incidents?limit=150&active_only=true", { signal: controller.signal });
            if (!res.ok) return;
            const data = await res.json();
            if (controller.signal.aborted || isDestroyed || !Array.isArray(data)) return;
            allIncidents = data
                .filter((inc) => inc && inc.incident_no && inc.timestamp)
                .map((inc) => ({
                    id: inc.incident_no,
                    renderKey: getIncidentRenderKey(inc),
                    timestamp: inc.timestamp,
                    time: formatTimestamp(inc.timestamp),
                    description: inc.description || t("fallback.descriptionUnavailable"),
                    location: inc.location || t("fallback.unknownLocation"),
                    neighborhood: inc.neighborhood || "",
                    latitude: inc.latitude ?? null,
                    longitude: inc.longitude ?? null,
                    type: inc.type || t("fallback.incidentType"),
                    active: Boolean(inc.active),
                    source: inc.source || "",
                    details: Array.isArray(inc.Details) ? inc.Details : [],
                    severity: inc.severity ?? null,
                }));
            updateMarkers();
        } catch (err) {
            if (!controller.signal.aborted) console.error("MapTab: Error fetching incidents:", err);
        } finally {
            if (incidentsController === controller) incidentsController = undefined;
        }
    }

    function startPolling() {
        if (!map || refreshInterval || !isVisible || document.hidden) return;
        fetchAllIncidents();
        refreshInterval = setInterval(fetchAllIncidents, 60000);
    }

    function stopPolling() {
        incidentsController?.abort();
        incidentsController = undefined;
        clearInterval(refreshInterval);
        refreshInterval = undefined;
    }

    function scheduleMapResize() {
        if (!map || resizeFrame) return;

        void tick().then(() => {
            if (!map || resizeFrame || isDestroyed) return;
            resizeFrame = requestAnimationFrame(() => {
                resizeFrame = 0;
                if (!map || !mapContainer) return;
                const bounds = mapContainer.getBoundingClientRect();
                if (bounds.width === 0 || bounds.height === 0) return;
                map.resize();
                map.triggerRepaint();
            });
        });
    }

    function startResizeObserver() {
        if (resizeObserver || !("ResizeObserver" in window) || !mapContainer) return;
        resizeObserver = new ResizeObserver(scheduleMapResize);
        resizeObserver.observe(mapContainer);
    }

    function stopResizeObserver() {
        resizeObserver?.disconnect();
        resizeObserver = undefined;
        if (resizeFrame) {
            cancelAnimationFrame(resizeFrame);
            resizeFrame = 0;
        }
    }

    $: if (isVisible && $pageVisible && map) {
        startPolling();
        scheduleMapResize();
    } else {
        stopPolling();
    }

    $: {
        // Show all active incidents, filtered by source
        activeIncidents = allIncidents
            .filter((inc) => {
                if (inc.latitude == null || inc.longitude == null) return false;
                // Source filter
                if (inc.source === "CHP" && !showCHP) return false;
                if (inc.source === "SDPD" && !showSDPD) return false;
                if (inc.source === "SDSO" && !showSDSO) return false;
                if (inc.source === "SDFD" && !showSDFD) return false;
                
                return inc.active;
            })
            .sort(
                (a, b) =>
                    new Date(b.timestamp).getTime() -
                    new Date(a.timestamp).getTime(),
            );

        // Call updateMarkers whenever activeIncidents changes
        if (map) {
            updateMarkers(activeIncidents);
        }
    }

    // Reactively fly to a specific incident when mapPanTo is set
    $: if (map && $mapPanTo) {
        const panData = $mapPanTo;
        $mapPanTo = null; // Reset early
        // The container might just have been unhidden, so wait a tick, resize, then fly
        setTimeout(() => {
            if (map) {
                map.resize();
                const targetZoom = getIncidentFocusZoom(
                    panData.preserveZoom,
                );
                map.flyTo({
                    center: [panData.longitude, panData.latitude],
                    zoom: targetZoom,
                    pitch: MAP_PITCH,
                    bearing: MAP_BEARING,
                    duration: motionDuration(1200),
                });
                $activeMarkerId = panData.id;
            }
        }, 150);
    }

    onMount(() => {
        isDestroyed = false;

        async function initializeMap() {
            mapLoadError = "";
            const libraries = await loadMapLibraries();
            maplibregl = libraries.maplibregl;
            if (isDestroyed || map || !mapContainer) return;

        // DEFCON-style dark command center map
        /** @type {import('maplibre-gl').StyleSpecification} */
            const style = {
            version: 8,
            name: "DEFCON Dark",
            light: {
                anchor: "viewport",
                color: "#d7e3ff",
                intensity: 0.35,
                position: [1.2, 210, 35],
            },
            sources: {
                sandiego: {
                    type: "vector",
                    url: "pmtiles://" + PMTILES_URL,
                },
            },
            // Local self-hosted glyphs (Noto Sans PBF fonts)
            glyphs: "/fonts/{fontstack}/{range}.pbf",
            layers: [
                // ── Background ──
                {
                    id: "background",
                    type: "background",
                    paint: {
                        "background-color": "rgba(8, 9, 10, 0)",
                    },
                },
                // ── Earth / Land ──
                {
                    id: "earth",
                    source: "sandiego",
                    "source-layer": "earth",
                    type: "fill",
                    paint: {
                        "fill-color": "#0f1114",
                    },
                },
                // ── Landcover (forests, grass at low zoom) ──
                {
                    id: "landcover",
                    source: "sandiego",
                    "source-layer": "landcover",
                    type: "fill",
                    paint: {
                        "fill-color": "#0d120e",
                        "fill-opacity": 0.5,
                    },
                },
                // ── Landuse (parks, industrial, etc.) ──
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
                        "recreation_ground",
                        "cemetery",
                        "forest",
                        "wood",
                    ],
                    type: "fill",
                    paint: {
                        "fill-color": "#0a1a0e",
                        "fill-opacity": 0.6,
                    },
                },
                {
                    id: "landuse_industrial",
                    source: "sandiego",
                    "source-layer": "landuse",
                    filter: [
                        "in",
                        "kind",
                        "industrial",
                        "railway",
                        "commercial",
                    ],
                    type: "fill",
                    paint: {
                        "fill-color": "#12100e",
                        "fill-opacity": 0.4,
                    },
                },
                {
                    id: "landuse_school",
                    source: "sandiego",
                    "source-layer": "landuse",
                    filter: [
                        "in",
                        "kind",
                        "school",
                        "university",
                        "college",
                        "hospital",
                    ],
                    type: "fill",
                    paint: {
                        "fill-color": "#110e14",
                        "fill-opacity": 0.4,
                    },
                },
                // ── Water ──
                {
                    id: "water",
                    source: "sandiego",
                    "source-layer": "water",
                    type: "fill",
                    paint: {
                        "fill-color": "#060d14",
                    },
                },
                // ── Boundaries ──
                {
                    id: "boundaries",
                    source: "sandiego",
                    "source-layer": "boundaries",
                    type: "line",
                    paint: {
                        "line-color": "#1a3a2a",
                        "line-width": 1,
                        "line-dasharray": [4, 3],
                        "line-opacity": 0.6,
                    },
                },
                // ── Buildings ──
                {
                    id: "buildings",
                    source: "sandiego",
                    "source-layer": "buildings",
                    type: "fill-extrusion",
                    minzoom: 13,
                    paint: {
                        "fill-extrusion-color": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            13,
                            "#141922",
                            16,
                            "#252d39",
                        ],
                        "fill-extrusion-height": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            13,
                            0,
                            15,
                            ["case", ["has", "height"], ["get", "height"], 12],
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
                        "fill-extrusion-opacity": 0.74,
                        "fill-extrusion-vertical-gradient": true,
                    },
                },
                // ── Roads (bottom to top: minor → major → highway) ──
                {
                    id: "road_other",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "other"],
                    type: "line",
                    minzoom: 14,
                    paint: {
                        "line-color": "#1a1d22",
                        "line-width": 0.5,
                    },
                },
                {
                    id: "road_minor",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "minor_road"],
                    type: "line",
                    minzoom: 12,
                    paint: {
                        "line-color": "#222730",
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
                    id: "road_medium",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "medium_road"],
                    type: "line",
                    paint: {
                        "line-color": "#2a3040",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            8,
                            0.5,
                            14,
                            3,
                        ],
                    },
                },
                {
                    id: "road_major",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "major_road"],
                    type: "line",
                    paint: {
                        "line-color": "#353e52",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            6,
                            0.5,
                            12,
                            2,
                            16,
                            4,
                        ],
                    },
                },
                // Highway casing (outline glow)
                {
                    id: "road_highway_casing",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "highway"],
                    type: "line",
                    paint: {
                        "line-color": "#1a3366",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            6,
                            2,
                            12,
                            5,
                            16,
                            8,
                        ],
                        "line-opacity": 0.4,
                    },
                },
                // Highway fill
                {
                    id: "road_highway",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "highway"],
                    type: "line",
                    paint: {
                        "line-color": "#2a55cc",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            6,
                            1,
                            12,
                            2.5,
                            16,
                            5,
                        ],
                        "line-opacity": 0.85,
                    },
                },
                // ── Road Labels ──
                {
                    id: "road_label_highway",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["all", ["==", "kind", "highway"], ["has", "ref"]],
                    type: "symbol",
                    minzoom: 7,
                    layout: {
                        "text-field": "{ref}",
                        "text-font": ["Noto Sans Medium"],
                        "text-size": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            7,
                            8,
                            10,
                            10,
                            14,
                            12,
                        ],
                        "symbol-placement": "line",
                        "symbol-spacing": 400,
                        "text-rotation-alignment": "map",
                        "text-max-angle": 30,
                    },
                    paint: {
                        "text-color": "#7799ee",
                        "text-halo-color": "#0a0e16",
                        "text-halo-width": 2,
                    },
                },
                {
                    id: "road_label_major",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: [
                        "all",
                        ["in", "kind", "major_road", "medium_road"],
                        ["has", "name"],
                    ],
                    type: "symbol",
                    minzoom: 11,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Regular"],
                        "text-size": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            11,
                            8,
                            14,
                            11,
                            16,
                            13,
                        ],
                        "symbol-placement": "line",
                        "symbol-spacing": 300,
                        "text-rotation-alignment": "map",
                        "text-max-angle": 25,
                    },
                    paint: {
                        "text-color": "#667788",
                        "text-halo-color": "#080a0e",
                        "text-halo-width": 1.5,
                    },
                },
                {
                    id: "road_label_minor",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: [
                        "all",
                        ["==", "kind", "minor_road"],
                        ["has", "name"],
                    ],
                    type: "symbol",
                    minzoom: 14,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Regular"],
                        "text-size": 10,
                        "symbol-placement": "line",
                        "symbol-spacing": 250,
                        "text-rotation-alignment": "map",
                        "text-max-angle": 25,
                    },
                    paint: {
                        "text-color": "#556677",
                        "text-halo-color": "#080a0e",
                        "text-halo-width": 1,
                    },
                },
                // ── Water Labels ──
                {
                    id: "water_label",
                    source: "sandiego",
                    "source-layer": "water",
                    filter: ["has", "name"],
                    type: "symbol",
                    minzoom: 11,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Regular"],
                        "text-size": 11,
                        "text-letter-spacing": 0.15,
                    },
                    paint: {
                        "text-color": "#2a4466",
                        "text-halo-color": "#060d14",
                        "text-halo-width": 1,
                    },
                },
                // ── POI Labels ──
                {
                    id: "poi_label",
                    source: "sandiego",
                    "source-layer": "pois",
                    filter: ["has", "name"],
                    type: "symbol",
                    minzoom: 14,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Regular"],
                        "text-size": 10,
                        "text-offset": [0, 0.8],
                        "text-anchor": "top",
                    },
                    paint: {
                        "text-color": "#556b5f",
                        "text-halo-color": "#080a0e",
                        "text-halo-width": 1,
                    },
                },
                // ── Place Labels (cities, towns, neighborhoods) ──
                {
                    id: "place_label_neighbourhood",
                    source: "sandiego",
                    "source-layer": "places",
                    type: "symbol",
                    filter: [
                        "in",
                        "kind",
                        "neighbourhood",
                        "suburb",
                        "locality",
                    ],
                    minzoom: 10,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Regular"],
                        "text-size": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            10,
                            9,
                            13,
                            12,
                            15,
                            14,
                        ],
                        "text-transform": "uppercase",
                        "text-letter-spacing": 0.1,
                        "text-allow-overlap": true,
                    },
                    paint: {
                        "text-color": "#cccccc",
                        "text-halo-color": "#080a0e",
                        "text-halo-width": 1.5,
                    },
                },
                {
                    id: "place_label_town",
                    source: "sandiego",
                    "source-layer": "places",
                    type: "symbol",
                    filter: ["in", "kind", "town", "village", "hamlet"],
                    minzoom: 7,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Medium"],
                        "text-size": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            7,
                            10,
                            10,
                            13,
                            14,
                            17,
                        ],
                        "text-transform": "uppercase",
                        "text-letter-spacing": 0.08,
                        "text-allow-overlap": true,
                    },
                    paint: {
                        "text-color": "#e0e0e0",
                        "text-halo-color": "#080a0e",
                        "text-halo-width": 2,
                    },
                },
                {
                    id: "place_label_city",
                    source: "sandiego",
                    "source-layer": "places",
                    type: "symbol",
                    filter: ["in", "kind", "city", "state", "country"],
                    minzoom: 4,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Medium"],
                        "text-size": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            4,
                            12,
                            8,
                            16,
                            12,
                            22,
                        ],
                        "text-transform": "uppercase",
                        "text-letter-spacing": 0.15,
                        "text-allow-overlap": true,
                    },
                    paint: {
                        "text-color": "#ffffff",
                        "text-halo-color": "#050a08",
                        "text-halo-width": 3,
                    },
                },
            ],
        };

            map = new maplibregl.Map({
                container: mapContainer,
                style: style,
                center: [-117.1611, 32.7157], // San Diego coordinates
                zoom: 10.8,
                pitch: MAP_PITCH,
                bearing: MAP_BEARING,
                minZoom: MIN_ZOOM,
                maxZoom: 18,
                maxPitch: 65,
                renderWorldCopies: false,
                hash: false,
                fadeDuration: 0,
                pixelRatio: Math.min(window.devicePixelRatio || 1, 2),
                maxTileCacheZoomLevels: 3,
            });

            map.setTransformConstrain(softConstrain);
            startResizeObserver();

            map.addControl(new maplibregl.NavigationControl(), "top-right");

            // Add geolocate control to the map
            map.addControl(
                new maplibregl.GeolocateControl({
                    positionOptions: {
                        enableHighAccuracy: true,
                    },
                    trackUserLocation: true,
                }),
                "top-right",
            );

            if (isVisible) {
                startPolling();
            }

            map.on("load", () => {
                mapReady = true;
                mapLoadError = "";
                scheduleMapResize();
                console.log("MapLibre GL map loaded with PMTiles — DEFCON theme");
            });

            map.on("error", (event) => {
                console.warn("MapTab: map resource failed to load", event?.error || event);
                if (!mapReady) {
                    mapLoadError = "Map tiles could not be loaded. Check your connection and try again.";
                }
            });

            // Close the active marker if the user clicks anywhere on the map
            map.on("click", () => {
                $activeMarkerId = null;
            });

            map.on("dragend", () => {
                snapBackToBounds(true);
            });
        }

        void initializeMap().catch((error) => {
            console.error("MapTab: failed to initialize map", error);
            mapLoadError = "The map could not start. Check your connection and try again.";
        });

        return () => {
            isDestroyed = true;
            stopPolling();
            stopResizeObserver();
            if (map) {
                // Remove all markers before destroying map
                Object.values(markers).forEach((markerEntry) => {
                    markerEntry.marker.remove();
                    unmount(markerEntry.component);
                });
                markers = {};
                map.remove();
                map = undefined;
            }
        };
    });

    function updateMarkers(incidentsToRender) {
        if (!map || !incidentsToRender) return;

        const activeIds = new Set(incidentsToRender.map((i) => i.renderKey));

        // Remove old markers that are no longer active
        for (const [id, markerObj] of Object.entries(markers)) {
            if (!activeIds.has(id)) {
                markerObj.marker.remove();
                unmount(markerObj.component);
                delete markers[id];
            }
        }

        // Add or update markers
        incidentsToRender.forEach((inc) => {
            const dataKey = getMarkerDataKey(inc);
            if (!markers[inc.renderKey]) {
                // Create a container element for the Svelte component
                const el = document.createElement("div");

                // Instantiate the component using Svelte 5 mount()
                const component = mount(IncidentMarker, {
                    target: el,
                    props: { incident: inc },
                });

                // Create and add MapLibre marker
                const marker = new maplibregl.Marker({ element: el })
                    .setLngLat([inc.longitude, inc.latitude])
                    .addTo(map);

                markers[inc.renderKey] = { marker, component, element: el, dataKey };
            } else {
                const existing = markers[inc.renderKey];
                existing.marker.setLngLat([inc.longitude, inc.latitude]);
                if (existing.dataKey !== dataKey) {
                    // Unchanged polling results should not rebuild marker DOM.
                    unmount(existing.component);
                    existing.element.innerHTML = "";
                    existing.component = mount(IncidentMarker, {
                        target: existing.element,
                        props: { incident: inc },
                    });
                    existing.dataKey = dataKey;
                }
            }
        });
    }

    function panToIncident(incident) {
        if (map && incident.longitude != null && incident.latitude != null) {
            map.flyTo({
                center: [incident.longitude, incident.latitude],
                zoom: getIncidentFocusZoom(),
                pitch: MAP_PITCH,
                bearing: MAP_BEARING,
                duration: motionDuration(1200),
            });
            $activeMarkerId = incident.renderKey;
        }
    }

    function getSourceColor(source) {
        if (source === "CHP") return "#ffaa33";
        if (source === "SDPD") return "#3366ff";
        if (source === "SDSO") return "#00ccff"; // Distinct cyan color for sheriff
        if (source === "SDFD") return "#ff3333";
        return "#888888";
    }
</script>

<div class="map-layout">
    <div class="map-wrapper">
        <div class="map-container" bind:this={mapContainer}></div>
        {#if !mapReady}
            <div class:error={Boolean(mapLoadError)} class="map-status" role="status">
                {mapLoadError || "Loading map…"}
            </div>
        {/if}
        <div class="map-filters">
            <button
                class="filter-btn"
                class:active={showCHP}
                on:click={() => toggleFilter("CHP")}
                type="button"
            >
                <span
                    class="filter-dot"
                    style="background: {showCHP ? '#ffaa33' : '#555'};"
                ></span>
                TRAFFIC
            </button>
            <button
                class="filter-btn"
                class:active={showSDPD && showSDSO}
                on:click={() => toggleFilter("POLICE")}
                type="button"
            >
                <span
                    class="filter-dot"
                    style="background: {(showSDPD && showSDSO) ? 'linear-gradient(135deg, #3366ff 50%, #00ccff 50%)' : '#555'};"
                ></span>
                POLICE / SHERIFF
            </button>
            <button
                class="filter-btn"
                class:active={showSDFD}
                on:click={() => toggleFilter("SDFD")}
                type="button"
            >
                <span
                    class="filter-dot"
                    style="background: {showSDFD ? '#ff3333' : '#555'};"
                ></span>
                FIRE
            </button>
        </div>
    </div>

    <div class="incident-log">
        <div class="log-header">
            <h3>INCIDENT LOG ({activeIncidents.length})</h3>
        </div>
        <div class="log-list">
            {#each activeIncidents as incident (incident.renderKey)}
                <button
                    class="log-item"
                    class:selected={$activeMarkerId === incident.id || $activeMarkerId === incident.renderKey}
                    class:inactive={!incident.active}
                    on:click={() => panToIncident(incident)}
                    type="button"
                    in:fade={{ duration: 200 }}
                >
                    <div class="log-item-header">
                        <span class="log-time"
                            >{formatTime(incident.timestamp)}</span
                        >
                        <span
                            class="log-source"
                            style="color: {getSourceColor(incident.source)}"
                        >
                            [{incident.source || "UNK"}]
                        </span>
                    </div>
                    <div class="log-desc">
                        {incident.type || incident.description.split(" - ")[0]}
                    </div>
                    <div class="log-loc">
                        {incident.neighborhood &&
                        incident.neighborhood !== "N/A"
                            ? incident.neighborhood
                            : incident.location}
                    </div>
                </button>
            {/each}
            {#if activeIncidents.length === 0}
                <div class="empty-log">NO ACTIVE INCIDENTS</div>
            {/if}
        </div>
    </div>
</div>

<style>
    .map-layout {
        display: block;
        height: min(72vh, 760px);
        min-height: 500px;
        margin-bottom: 1.25rem;
    }

    .map-wrapper {
        position: relative;
        height: 100%;
    }

    .map-container {
        width: 100%;
        height: 100%;
        min-height: 400px;
        border-radius: var(--radius-xl);
        corner-shape: squircle;
        border: 1px solid var(--border-color);
        overflow: hidden;
        position: relative;
        background:
            radial-gradient(
                circle at 50% 45%,
                rgba(51, 102, 255, 0.14) 0%,
                rgba(8, 9, 10, 0.94) 58%,
                #040506 100%
            );
        box-shadow: var(--shadow-md);
    }

    .map-status {
        position: absolute;
        left: 50%;
        top: 50%;
        z-index: 2;
        max-width: min(420px, calc(100% - 48px));
        padding: 0.7rem 0.9rem;
        transform: translate(-50%, -50%);
        border: 1px solid rgba(136, 170, 255, 0.22);
        border-radius: 12px;
        corner-shape: squircle;
        color: var(--text-muted);
        background: #151922;
        box-shadow: var(--shadow-sm);
        font-size: 0.82rem;
        text-align: center;
        pointer-events: none;
    }

    .map-status.error {
        color: #fecaca;
        border-color: rgba(248, 113, 113, 0.4);
    }

    @media (min-width: 1024px) {
        .map-layout {
            display: flex;
            flex-direction: row;
            gap: 1rem;
            height: min(72vh, 760px);
            min-height: 400px;
        }

        .map-wrapper {
            flex: 1;
            height: 100%;
            min-height: 400px;
        }

        .map-container {
            height: 100%;
        }
    }

    .map-filters {
        position: absolute;
        top: 12px;
        left: 12px;
        display: flex;
        gap: 7px;
        z-index: 1000;
        flex-wrap: wrap;
        max-width: calc(100% - 24px);
    }

    .filter-btn {
        display: flex;
        align-items: center;
        gap: 6px;
        min-height: 38px;
        padding: 7px 12px;
        background: #1b1f28;
        border: 1px solid rgba(255,255,255,.14);
        border-radius: 12px;
        corner-shape: squircle;
        color: #a5adba;
        font-size: 0.72rem;
        font-weight: 680;
        cursor: pointer;
        transition: all 0.15s ease;
        box-shadow: var(--shadow-sm);
    }

    .filter-btn.active {
        color: #f4f7fb;
        border-color: rgba(136, 170, 255, 0.5);
        background: #10141c;
    }

    .filter-btn:hover {
        border-color: rgba(136, 170, 255, 0.6);
        background: #111d2c;
    }

    .filter-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }

    :global(.maplibregl-ctrl-group) {
        background: #1b1f28 !important;
        border: 1px solid rgba(255,255,255,.14) !important;
        border-radius: 13px !important;
        corner-shape: squircle;
        overflow: hidden;
        box-shadow: var(--shadow-sm) !important;
    }

    :global(.maplibregl-ctrl-group button) {
        background: transparent !important;
        border-bottom: 1px solid rgba(255,255,255,.1) !important;
    }

    :global(.maplibregl-ctrl-group button:last-child) {
        border-bottom: none !important;
    }

    :global(.maplibregl-ctrl-icon) {
        filter: invert(1) sepia(0.3) hue-rotate(90deg);
    }

    :global(.maplibregl-ctrl-attrib) {
        background: rgba(0, 0, 0, 0.5) !important;
        color: #334433 !important;
        font-size: 10px !important;
    }

    :global(.maplibregl-ctrl-attrib a) {
        color: #446644 !important;
    }

    /* Incident Log Styles */
    .incident-log {
        background: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-xl);
        corner-shape: squircle;
        display: flex;
        flex-direction: column;
        height: 100%;
        overflow: hidden;
        box-shadow: var(--shadow-md);
    }

    @media (max-width: 1023px) {
        .incident-log {
            display: none;
        }
    }

    @media (min-width: 1024px) {
        .incident-log {
            width: 320px;
            flex-shrink: 0;
        }
    }

    @media (min-width: 1280px) {
        .incident-log {
            width: 380px;
        }
    }

    .log-header {
        padding: 16px 18px;
        background: var(--bg-surface-elevated);
        border-bottom: 1px solid var(--border-color);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .log-header h3 {
        margin: 0;
        font-size: 0.87rem;
        color: var(--text-main);
        letter-spacing: -0.01em;
    }

    .log-list {
        flex: 1;
        overflow-y: auto;
        padding: 8px;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .log-list::-webkit-scrollbar {
        width: 6px;
    }

    .log-list::-webkit-scrollbar-track {
        background: #05080c;
    }

    .log-list::-webkit-scrollbar-thumb {
        background: #2a3b5c;
        border-radius: 3px;
        corner-shape: squircle;
    }

    .log-item {
        width: 100%;
        color: inherit;
        text-align: left;
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        border-radius: 14px;
        corner-shape: squircle;
        padding: 9px 11px;
        cursor: pointer;
        transition: all 0.2s ease;
        position: relative;
    }

    .log-item:hover {
        background: var(--primary-lightest);
        border-color: rgba(136, 170, 255, 0.4);
        transform: translateX(4px);
    }

    .log-item.selected {
        background: var(--primary-lightest);
        border-color: rgba(136, 170, 255, 0.8);
        box-shadow: 0 8px 22px rgba(20,30,50,.12);
        border-left: 3px solid #88aaff;
    }

    .log-item.inactive {
        opacity: 0.65;
    }

    .log-item.inactive:hover {
        opacity: 0.9;
    }

    .log-item-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 4px;
        font-size: 0.7rem;
    }

    .log-time {
        color: #88aaff;
    }

    .log-source {
        font-weight: bold;
    }

    .log-desc {
        font-size: 0.75rem;
        color: var(--text-main);
        margin-bottom: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .log-loc {
        font-size: 0.65rem;
        color: var(--text-muted);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .empty-log {
        text-align: center;
        padding: 2rem 0;
        color: #445566;
        font-size: 0.8rem;
        letter-spacing: 0.1em;
    }

    @media (max-width: 640px) {
        .map-layout { height: 68vh; min-height: 430px; }
        .map-container { min-height: 430px; border-radius: 22px; corner-shape: squircle; }
        .filter-btn { padding: 7px 10px; font-size: .66rem; }
    }
</style>
