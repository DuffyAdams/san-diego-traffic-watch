<script>
  import { onMount } from "svelte";
  import { fade } from "./utils/motion.js";
  import { expandPanel } from "./utils/expandPanel.js";
  import { pageVisible } from "./stores/pageActivity.js";

  // Import components
  import Header from "./components/ui/Header.svelte";
  import HeadlineTicker from "./components/feed/HeadlineTicker.svelte";
  import SkeletonCard from "./components/feed/SkeletonCard.svelte";
  import PostCard from "./components/feed/PostCard.svelte";
  import ShareDialog from "./components/feed/ShareDialog.svelte";
  import ToastContainer from "./components/ui/ToastContainer.svelte";
  import ViewToggle from "./components/ui/ViewToggle.svelte";
  import SourceTabs from "./components/ui/SourceTabs.svelte";
  import SearchBar from "./components/ui/SearchBar.svelte";

  // Import utilities
  import {
    generateRandomUsername,
    debounce,
    retryWithBackoff,
  } from "./utils/helpers.js";

  // Import stores
  import { addToast } from "./stores/appStore.js";
  import { compareText, t } from "./utils/i18n.js";
  import { getCachedEntry, setCachedEntry } from "./utils/cache.js";
  import { buildIncidentsUrl, buildStatsUrl } from "./utils/apiUrls.js";
  import { buildPostFromIncident, fuzzyMatch, reconcileIncidents } from "./utils/incidents.js";
  import { loadMapLibraries } from "./utils/mapRuntime.js";

  /**
   * @typedef {Object} PostComment
   * @property {string} [id]
   * @property {string} username
   * @property {string} comment
   * @property {string} timestamp
   */

  /**
   * @typedef {Object} Incident
   * @property {string} [incident_no]
   * @property {string} [timestamp]
   * @property {string[]} [Details]
   * @property {string} [description]
   * @property {string} [location]
   * @property {string} [neighborhood]
   * @property {number | null} [latitude]
   * @property {number | null} [longitude]
   * @property {string} [map_filename]
   * @property {number} [likes]
   * @property {PostComment[]} [comments]
   * @property {string} [type]
   * @property {boolean} [active]
   * @property {number | null} [severity]
   * @property {boolean} [liked_by_user]
   * @property {string} [compositeId]
   */

  /**
   * @typedef {Object} Post
   * @property {string} id
   * @property {string} compositeId
   * @property {string[]} details
   * @property {string} timestamp
   * @property {string} time
   * @property {string} description
   * @property {boolean} showFullDescription
   * @property {string} location
   * @property {string} neighborhood
   * @property {number | null} latitude
   * @property {number | null} longitude
   * @property {string} image
   * @property {number} likes
   * @property {PostComment[]} comments
   * @property {string} newComment
   * @property {boolean} showComments
   * @property {string} type
   * @property {string} likeError
   * @property {string} commentError
   * @property {boolean} likeErrorAnimation
   * @property {boolean} active
   * @property {boolean} liking
   * @property {number | null} severity
   * @property {boolean} likedByUser
   */

  /**
   * @typedef {Object} IncidentStatsResponse
   * @property {number} eventsToday
   * @property {number} eventsLastHour
   * @property {number} eventsActive
   * @property {number} totalIncidents
   * @property {Record<string, number>} incidentsByType
   * @property {Record<string, number>} topLocations
   * @property {number[]} [hourlyData]
   * @property {number[] | null} [previousWeekHourlyData]
   * @property {number[] | null} [previousPeriodData]
   * @property {number} [historicalCurrentHourAverage]
   * @property {number} [historicalHourSampleCount]
   * @property {string} [generatedAt]
   */

  /**
   * @typedef {Object} StatsCacheEntry
   * @property {IncidentStatsResponse} data
   * @property {number} timestamp
   */

  /**
   * @typedef {Object} ApiCacheEntry
   * @property {Incident[]} data
   * @property {number} timestamp
   */

  /**
   * @typedef {Object} LikeResponse
   * @property {number} likes
   * @property {boolean} liked_by_user
   */

  /**
   * @typedef {Object} CommentResponse
   * @property {PostComment[]} comments
   */

  /** @typedef {CustomEvent<{ postId: string }>} PostIdEvent */
  /** @typedef {CustomEvent<{ post: Post, elements: HTMLElement[] }>} PostShareEvent */
  /** @typedef {CustomEvent<string>} StringDetailEvent */

  // State variables
  /** @type {Post[]} */
  let posts = [];
  /** @type {{ post: Post, elements: HTMLElement[] } | null} */
  let shareRequest = null;
  let loading = true;
  let hasLoadedFeed = false;
  let animateFeedEntrance = true;
  let darkMode = true;
  let accessibilityMode = false;
  let currentUsername = "";
  let postsPerPage = 15;
  let currentPage = 1;
  let loadingMore = false;
  let allPostsLoaded = false;
  /** @type {HTMLDivElement | null} */
  let scrollContainer = null;
  /** @type {string | null} */
  let lastCursor = null;
  /** @type {Set<string>} */
  let selectedTypes = new Set();
  /** @type {Set<string>} */
  let selectedLocations = new Set();
  let condensedView = false;
  /** @type {string | null} */
  let expandedPostId = null;
  let eventsToday = 0;
  let eventsLastHour = 0;
  let eventsActive = 0;
  let totalIncidents = 0;
  /** @type {Record<string, number>} */
  let incidentsByType = {};
  /** @type {Record<string, number>} */
  let topLocations = {};
  let showEventCounters = false;
  let showActiveOnly = false;
  let timeFilter = "day";
  let searchQuery = "";
  let suspendFeedMiniMaps = false;
  let miniMapSuspendScrollTop = 0;
  /** @type {Set<string>} */
  let seenCompositeKeys = new Set();
  /** @type {typeof import("./components/map/MapTab.svelte").default | null} */
  let MapTabComponent = null;
  /** @type {Promise<typeof import("./components/map/MapTab.svelte").default> | null} */
  let mapTabLoadPromise = null;
  let mapResourcesPreloadPromise = null;
  /** @type {typeof import("./components/stats/StatsPanel.svelte").default | null} */
  let StatsPanelComponent = null;
  /** @type {Promise<typeof import("./components/stats/StatsPanel.svelte").default> | null} */
  let statsPanelLoadPromise = null;
  /** @type {typeof import("./components/feed/PostTable.svelte").default | null} */
  let PostTableComponent = null;
  /** @type {Promise<typeof import("./components/feed/PostTable.svelte").default> | null} */
  let postTableLoadPromise = null;
  const ACCESSIBILITY_MODE_STORAGE_KEY = "accessibilityMode";

  /** @type {Post[]} */
  let displayPosts = [];
  $: displayPosts = searchQuery
      ? posts.filter((p) => {
          const searchSpace = `${p.description} ${p.location} ${p.type || ""} ${p.neighborhood || ""} ${p.id}`;
          return fuzzyMatch(searchQuery, searchSpace);
      })
      : posts;

  /** @type {number[]} */
  let hourlyData = [];
  let previousPeriodData = null;
  let historicalCurrentHourAverage = null;
  let historicalHourSampleCount = 0;
  let statsReferenceTime = "";

  // Data Source Management
  let activeSource = "all"; // 'all', 'CHP', 'SDPD', 'SDFD'

  /**
   * @param {string} source
   */
  function setSourceFilter(source) {
    if (activeSource === source) return;
    stopUpdateRequest();
    activeSource = source;
    if (source === "map") {
      currentController?.abort();
      currentRequestId++;
      loading = false;
      loadingMore = false;
      stopStatsRequest();
      void Promise.all([ensureMapTabLoaded(), preloadMapResources()]);
      return;
    }
    currentPage = 1;
    // Reset other filters as they might not apply
    // selectedTypes = new Set();
    // selectedLocations = new Set();
    fetchIncidents();
    if (shouldFetchStats()) fetchIncidentStats();
  }

  async function ensureMapTabLoaded() {
    if (MapTabComponent) return MapTabComponent;
    if (!mapTabLoadPromise) {
      mapTabLoadPromise = import("./components/map/MapTab.svelte").then(
        (module) => {
          MapTabComponent = module.default;
          return MapTabComponent;
        },
      );
    }
    return mapTabLoadPromise;
  }

  function preloadMapResources() {
    if (!mapResourcesPreloadPromise) {
      mapResourcesPreloadPromise = loadMapLibraries().catch((error) => {
        mapResourcesPreloadPromise = null;
        console.warn("Map resources could not be preloaded", error);
      });
    }
    return mapResourcesPreloadPromise;
  }

  async function ensureStatsPanelLoaded() {
    if (StatsPanelComponent) return StatsPanelComponent;
    if (!statsPanelLoadPromise) {
      statsPanelLoadPromise = import("./components/stats/StatsPanel.svelte").then(
        (module) => {
          StatsPanelComponent = module.default;
          return StatsPanelComponent;
        },
      );
    }
    return statsPanelLoadPromise;
  }

  async function ensurePostTableLoaded() {
    if (PostTableComponent) return PostTableComponent;
    if (!postTableLoadPromise) {
      postTableLoadPromise = import("./components/feed/PostTable.svelte").then(
        (module) => {
          PostTableComponent = module.default;
          return PostTableComponent;
        },
      );
    }
    return postTableLoadPromise;
  }

  // Network status
  let isOnline = true;
  let isFirstCheck = true;

  function updateOnlineStatus() {
    const previouslyOnline = isOnline;
    isOnline = navigator.onLine;
    if (!isOnline) {
      if (!isFirstCheck) {
        addToast(t("toast.offline"), "warning", 0);
      }
    } else {
      if (!isFirstCheck && !previouslyOnline) {
        addToast(t("toast.connectionRestored"), "success");
      }
      if (activeSource !== "map" && posts.length === 0) fetchIncidents();
      else if (!isFirstCheck && !previouslyOnline) checkForUpdates();
      if (shouldFetchStats()) fetchIncidentStats();
    }
    isFirstCheck = false;
  }

  // Caching and cancellation
  const API_CACHE_TTL_MS = 15000;
  const STATS_CACHE_TTL_MS = 30000;
  const MAX_API_CACHE_ENTRIES = 30;
  const MAX_STATS_CACHE_ENTRIES = 12;

  /** @type {Map<string, ApiCacheEntry>} */
  let apiCache = new Map();
  /** @type {AbortController | null} */
  let currentController = null;
  /** @type {Map<string, StatsCacheEntry>} */
  let statsCache = new Map();
  /** @type {AbortController | null} */
  let statsController = null;
  let currentRequestId = 0;
  let currentStatsRequestId = 0;
  let updateController = null;

  function stopUpdateRequest() {
    updateController?.abort();
    updateController = null;
  }

  function clearIncidentCaches() {
    stopUpdateRequest();
    apiCache.clear();
  }

  function clearAllClientCaches() {
    apiCache.clear();
    statsCache.clear();
  }

  function shouldFetchStats() {
    return showEventCounters && activeSource !== "map";
  }

  function stopStatsRequest() {
    if (!statsController) return;
    currentStatsRequestId++;
    statsController.abort();
    statsController = null;
  }

  function suspendMiniMapsUntilScroll() {
    suspendFeedMiniMaps = true;
    miniMapSuspendScrollTop =
      window.scrollY || document.documentElement.scrollTop || 0;
  }

  // Touch/swipe handling
  let touchStartX = 0;
  let touchEndX = 0;
  let touchStartY = 0;
  let touchEndY = 0;
  let swipeInProgress = false;
  let swipeIndicator = false;
  let swipeDirection = "";
  let swipeThreshold = 80;
  let verticalThreshold = 50;
  let suppressAutoLoadUntilScroll = false;
  let autoLoadUnlockScrollTop = 0;

  function pauseAutoLoadUntilUserScroll() {
    suppressAutoLoadUntilScroll = true;
    autoLoadUnlockScrollTop =
      window.scrollY || document.documentElement.scrollTop || 0;
  }

  function setCondensedView(nextView) {
    if (condensedView === nextView) return;
    condensedView = nextView;
    if (nextView) void ensurePostTableLoaded();
    pauseAutoLoadUntilUserScroll();
    if (showEventCounters) {
      showEventCounters = false;
      stopStatsRequest();
      suspendMiniMapsUntilScroll();
    }
  }

  function applyUserPreferences() {
    document.body.classList.toggle("dark-mode", darkMode);
    document.body.classList.toggle("accessibility-mode", accessibilityMode);
  }

  function toggleDarkMode() {
    darkMode = !darkMode;
    applyUserPreferences();
    localStorage.setItem("darkMode", darkMode.toString());
  }

  function toggleAccessibilityMode() {
    accessibilityMode = !accessibilityMode;
    applyUserPreferences();
    localStorage.setItem(ACCESSIBILITY_MODE_STORAGE_KEY, accessibilityMode.toString());
  }

  function toggleEventCounters() {
    showEventCounters = !showEventCounters;
    if (shouldFetchStats()) {
      void ensureStatsPanelLoaded();
      fetchIncidentStats();
    } else {
      stopStatsRequest();
    }
  }

  function toggleActiveOnly() {
    showActiveOnly = !showActiveOnly;
    currentPage = 1;
    fetchIncidents();
  }

  /**
   * @param {string} newFilter
   */
  function setTimeFilter(newFilter) {
    timeFilter = newFilter;
    // Don't destroy chart here to prevent flashing
    // statsCache = {}; // Removed to preserve cache
    fetchIncidentStats();
  }

  /**
   * @param {string} type
   */
  function filterByType(type) {
    if (selectedTypes.has(type)) {
      selectedTypes.delete(type);
    } else {
      selectedTypes.add(type);
    }
    selectedTypes = new Set(selectedTypes); // Trigger reactivity
    currentPage = 1;
    fetchIncidents();
  }

  /**
   * @param {string} location
   */
  function filterByLocation(location) {
    if (selectedLocations.has(location)) {
      selectedLocations.delete(location);
    } else {
      selectedLocations.add(location);
    }
    selectedLocations = new Set(selectedLocations); // Trigger reactivity
    currentPage = 1;
    fetchIncidents();
  }

  function resetTypeFilters() {
    selectedTypes = new Set();
    currentPage = 1;
    fetchIncidents();
  }

  function resetLocationFilters() {
    selectedLocations = new Set();
    currentPage = 1;
    fetchIncidents();
  }

  async function fetchIncidents() {
    stopUpdateRequest();
    const requestId = ++currentRequestId;
    const replaceFeed = currentPage === 1;

    if (currentController) {
      currentController.abort();
    }
    const controller = new AbortController();
    currentController = controller;
    const signal = controller.signal;

    try {
      // Keep the mounted feed and ticker until the replacement is ready.
      // Replaying height-based entrances on filter changes collapses the page.
      animateFeedEntrance = !hasLoadedFeed || !replaceFeed;
      if (replaceFeed) {
        loading = true;
        loadingMore = false;
      } else {
        loadingMore = true;
      }

      const url = buildIncidentsUrl({
        limit: postsPerPage,
        cursor: currentPage > 1 ? lastCursor : null,
        types: selectedTypes,
        locations: selectedLocations,
        activeOnly: showActiveOnly,
        source: activeSource,
      });

      const cacheKey = url;
      const cachedData = getCachedEntry(apiCache, cacheKey, API_CACHE_TTL_MS);
      if (cachedData) {
        if (requestId === currentRequestId) processIncidents(cachedData, replaceFeed);
        return;
      }

      const fetchFn = async () => {
        const res = await fetch(url, { signal });
        if (!res.ok) {
          throw new Error(
            `Failed to fetch incidents: ${res.status} ${res.statusText}`,
          );
        }
        return await res.json();
      };

      /** @type {Incident[]} */
      const incidents = await retryWithBackoff(fetchFn, 3, 1000);

      if (requestId !== currentRequestId) {
        return;
      }

      if (!Array.isArray(incidents)) throw new Error("Invalid incidents data: expected array");
      setCachedEntry(apiCache, cacheKey, incidents, MAX_API_CACHE_ENTRIES);
      processIncidents(incidents, replaceFeed);
    } catch (err) {
      if (!signal.aborted && requestId === currentRequestId && (!(err instanceof Error) || err.name !== "AbortError")) {
        console.error("Error fetching incidents:", err);
        addToast(
          t("toast.failedLoadIncidents"),
          "error",
        );
        if (replaceFeed) {
          // Do not leave the previous source's results under a new source label.
          seenCompositeKeys.clear();
          lastCursor = null;
          allPostsLoaded = true;
          hasLoadedFeed = true;
          posts = [
            {
              id: "error-fallback",
              compositeId: "error-fallback",
              timestamp: new Date().toISOString(),
              time: t("fallback.error"),
              description: t("state.loadIncidentsUnavailable"),
              showFullDescription: false,
              location: t("fallback.notAvailable"),
              neighborhood: "",
              latitude: null,
              longitude: null,
              image: "",
              likes: 0,
              comments: [],
              newComment: "",
              showComments: false,
              type: t("fallback.error"),
              likeError: "",
              commentError: "",
              likeErrorAnimation: false,
              active: false,
              liking: false,
              severity: null,
              likedByUser: false,
            },
          ];
        }
      }
    } finally {
      if (requestId === currentRequestId) {
        loading = false;
        loadingMore = false;
      }
      if (currentController === controller) {
        currentController = null;
      }
    }
  }

  /**
   * @param {Incident[]} incidents
   * @param {boolean} replaceFeed
   */
  function processIncidents(incidents, replaceFeed) {
    if (!Array.isArray(incidents)) {
      console.error("Invalid incidents data: expected array");
      addToast(t("toast.invalidIncidentData"), "error");
      return;
    }

    // Reset pagination only when the winning request commits its results.
    if (replaceFeed) {
      seenCompositeKeys.clear();
      lastCursor = null;
    }
    const newProcessedPosts = incidents
      .filter((incident) => {
        if (!incident || typeof incident !== "object") return false;
        if (
          !incident.incident_no ||
          !incident.timestamp
          // Removed map_filename requirement to support sources without maps
          // || !incident.map_filename
        ) {
          return false;
        }
        return true;
      })
      .filter((incident) => {
        const duplicateKey = `${incident.incident_no}-${incident.timestamp}-${incident.location}`;
        if (seenCompositeKeys.has(duplicateKey)) {
          return false;
        }
        seenCompositeKeys.add(duplicateKey);
        return true;
      })
      .map((incident) => buildPostFromIncident(incident));

    const filteredPosts = showActiveOnly
      ? newProcessedPosts.filter((p) => p.active)
      : newProcessedPosts;

    // Sort by timestamp (newest first) after merging to ensure correct order
    posts = [...(replaceFeed ? [] : posts), ...filteredPosts].sort((a, b) => {
      const timeA = new Date(a.timestamp).getTime();
      const timeB = new Date(b.timestamp).getTime();
      if (timeB !== timeA) return timeB - timeA;
      // Tie-breaker: use ID if timestamps are identical
      return compareText(b.id, a.id);
    });

    if (incidents.length > 0) {
      const lastIncident = incidents[incidents.length - 1];
      lastCursor = `${lastIncident.timestamp}|${lastIncident.incident_no}`;
    }

    allPostsLoaded = incidents.length < postsPerPage;
    hasLoadedFeed = true;
  }

  function loadMorePosts() {
    if (activeSource === "map" || loading || loadingMore || allPostsLoaded) return;
    loadingMore = true;
    currentPage++;
    fetchIncidents();
  }

  const debouncedHandleScroll = debounce(() => {
    const scrollTop = window.scrollY || document.documentElement.scrollTop;
    const scrollHeight = document.documentElement.scrollHeight;
    const clientHeight = window.innerHeight;
    const scrollBottom = scrollHeight - scrollTop - clientHeight;

    if (suppressAutoLoadUntilScroll) {
      if (Math.abs(scrollTop - autoLoadUnlockScrollTop) <= 24) {
        return;
      }
      suppressAutoLoadUntilScroll = false;
    }

    if (
      suspendFeedMiniMaps &&
      Math.abs(scrollTop - miniMapSuspendScrollTop) > 24
    ) {
      suspendFeedMiniMaps = false;
    }

    if (scrollBottom < 600 && !loadingMore && !allPostsLoaded) {
      loadMorePosts();
    }
  }, 100);

  function forceLoadMore() {
    if (activeSource === "map" || loading || allPostsLoaded || loadingMore) return;
    currentPage++;
    fetchIncidents();
  }

  async function fetchIncidentStats() {
    const requestId = ++currentStatsRequestId;

    if (statsController) {
      statsController.abort();
    }
    const controller = new AbortController();
    statsController = controller;
    const signal = controller.signal;

    try {
      const url = buildStatsUrl(timeFilter, activeSource);

      const cacheKey = url;
      const cachedStats = getCachedEntry(
        statsCache,
        cacheKey,
        STATS_CACHE_TTL_MS,
      );
      if (cachedStats) {
        if (requestId !== currentStatsRequestId) return;
        eventsToday = cachedStats.eventsToday;
        eventsLastHour = cachedStats.eventsLastHour;
        eventsActive = cachedStats.eventsActive;
        totalIncidents = cachedStats.totalIncidents;

        incidentsByType = Object.fromEntries(
          Object.entries(cachedStats.incidentsByType).sort(
            ([, a], [, b]) => b - a,
          ),
        );
        topLocations = Object.fromEntries(
          Object.entries(cachedStats.topLocations).sort(
            ([, a], [, b]) => b - a,
          ),
        );
        // Important: Create new array reference for caching to trigger Svelte reactivity
        hourlyData = (cachedStats.hourlyData || []).map(Number);
        previousPeriodData = cachedStats.previousPeriodData ??
          (timeFilter === "day" ? cachedStats.previousWeekHourlyData ?? null : null);
        historicalCurrentHourAverage =
          cachedStats.historicalCurrentHourAverage ?? null;
        historicalHourSampleCount = cachedStats.historicalHourSampleCount ?? 0;
        statsReferenceTime = cachedStats.generatedAt || "";
        return;
      }

      const fetchFn = async () => {
        const res = await fetch(url, { signal });
        if (!res.ok) {
          throw new Error(
            `Failed to fetch incident stats: ${res.status} ${res.statusText}`,
          );
        }
        return await res.json();
      };

      /** @type {IncidentStatsResponse} */
      const stats = await retryWithBackoff(fetchFn, 3, 1000);

      if (signal.aborted || requestId !== currentStatsRequestId) {
        return;
      }

      setCachedEntry(statsCache, cacheKey, stats, MAX_STATS_CACHE_ENTRIES);

      eventsToday = stats.eventsToday;
      eventsLastHour = stats.eventsLastHour;
      eventsActive = stats.eventsActive;
      totalIncidents = stats.totalIncidents;
      hourlyData = (stats.hourlyData || []).map(Number);
      previousPeriodData = stats.previousPeriodData ??
        (timeFilter === "day" ? stats.previousWeekHourlyData ?? null : null);
      historicalCurrentHourAverage = stats.historicalCurrentHourAverage ?? null;
      historicalHourSampleCount = stats.historicalHourSampleCount ?? 0;
      statsReferenceTime = stats.generatedAt || "";

      incidentsByType = Object.fromEntries(
        Object.entries(stats.incidentsByType).sort(([, a], [, b]) => b - a),
      );
      topLocations = Object.fromEntries(
        Object.entries(stats.topLocations).sort(([, a], [, b]) => b - a),
      );
    } catch (err) {
      if (!signal.aborted && requestId === currentStatsRequestId && (!(err instanceof Error) || err.name !== "AbortError")) {
        console.error("Error fetching incident stats:", err);
        addToast(t("toast.failedLoadIncidentStats"), "error");
      }
    } finally {
      if (requestId === currentStatsRequestId) {
        statsController = null;
      }
    }
  }

  /**
   * @param {string} postId
   */
  async function likePost(postId) {
    stopUpdateRequest();
    const post = posts.find((p) => p.id === postId);
    if (!post || post.liking) return;

    posts = posts.map((p) => (p.id === postId ? { ...p, liking: true } : p));

    const originalLikes = post.likes;
    const wasLiked = Boolean(post.likedByUser);
    const nextLikes = Math.max(0, originalLikes + (wasLiked ? -1 : 1));

    posts = posts.map((p) =>
      p.id === postId
        ? {
            ...p,
            likes: nextLikes,
            likedByUser: !wasLiked,
            likeError: "",
            likeErrorAnimation: false,
          }
        : p,
    );

    try {
      const method = wasLiked ? "DELETE" : "POST";
      const fetchFn = async () => {
        const res = await fetch(`/api/incidents/${postId}/like`, { method });
        if (!res.ok) {
          throw new Error(`Failed to ${wasLiked ? "unlike" : "like"} post`);
        }
        return await res.json();
      };

      /** @type {LikeResponse} */
      const data = await retryWithBackoff(fetchFn, 2, 500);
      clearIncidentCaches();
      posts = posts.map((p) =>
        p.id === postId
          ? {
              ...p,
              likes: data.likes,
              likedByUser: Boolean(data.liked_by_user),
              likeError: "",
              liking: false,
            }
          : p,
      );
    } catch (err) {
      console.error("Error updating like:", err);
      addToast(
        wasLiked ? t("toast.failedUnlikePost") : t("toast.failedLikePost"),
        "error",
      );
      posts = posts.map((p) =>
        p.id === postId
          ? {
              ...p,
              likes: originalLikes,
              likedByUser: wasLiked,
              liking: false,
            }
          : p,
      );
    }
  }

  /**
   * @param {string} postId
   */
  function toggleComments(postId) {
    posts = posts.map((post) =>
      post.id === postId ? { ...post, showComments: !post.showComments } : post,
    );
  }

  /**
   * @param {string} postId
   * @param {string | null} [commentContent=null]
   */
  async function submitComment(postId, commentContent = null) {
    stopUpdateRequest();
    const post = posts.find((p) => p.id === postId);
    const commentText =
      commentContent !== null ? commentContent : post?.newComment;

    if (!post || !commentText || commentText.trim() === "") return;

    const userComments = post.comments.filter(
      (c) => c.username === currentUsername,
    );
    if (userComments.length >= 2) {
      addToast(t("toast.commentLimitReached"), "warning");
      return;
    }

    const newCommentObj = {
      username: currentUsername,
      comment: commentText.trim(),
      timestamp: new Date().toISOString(),
    };

    const originalComments = [...post.comments];
    const originalNewComment = post.newComment;

    const optimisticComment = { ...newCommentObj, id: `temp-${Date.now()}` };
    posts = posts.map((p) =>
      p.id === postId
        ? {
            ...p,
            comments: [...p.comments, optimisticComment],
            newComment: "",
            commentError: "",
          }
        : p,
    );

    try {
      const fetchFn = async () => {
        const res = await fetch(`/api/incidents/${postId}/comment`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(newCommentObj),
        });
        if (!res.ok) {
          throw new Error(`Failed to submit comment`);
        }
        return await res.json();
      };

      /** @type {CommentResponse} */
      const data = await retryWithBackoff(fetchFn, 2, 500);
      clearIncidentCaches();
      posts = posts.map((p) =>
        p.id === postId
          ? { ...p, comments: data.comments, newComment: "", commentError: "" }
          : p,
      );
      addToast(t("toast.commentAdded"), "success");
    } catch (err) {
      console.error("Error submitting comment:", err);
      addToast(t("toast.failedSubmitComment"), "error");
      posts = posts.map((p) =>
        p.id === postId
          ? {
              ...p,
              comments: originalComments,
              newComment: originalNewComment,
              commentError: "Failed to submit comment",
            }
          : p,
      );
    }
  }

  /**
   * @param {string} postId
   */
  function toggleDescription(postId) {
    posts = posts.map((post) =>
      post.id === postId
        ? { ...post, showFullDescription: !post.showFullDescription }
        : post,
    );
  }

  /**
   * @param {string} postId
   */
  function toggleExpand(postId) {
    expandedPostId = expandedPostId === postId ? null : postId;
  }

  /**
   * @param {TouchEvent} e
   */
  function handleTouchStart(e) {
    if (activeSource === "map") return;
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
    touchEndX = touchStartX;
    touchEndY = touchStartY;
    swipeInProgress = true;
  }

  /**
   * @param {TouchEvent} e
   */
  function handleTouchMove(e) {
    if (activeSource === "map") return;
    if (!swipeInProgress) return;

    touchEndX = e.touches[0].clientX;
    touchEndY = e.touches[0].clientY;

    const diffX = touchStartX - touchEndX;
    const diffY = touchEndY - touchStartY;

    if (Math.abs(diffX) > 20 && Math.abs(diffY) < verticalThreshold) {
      const nextDirection = diffX > 0 ? "left" : "right";
      if (!swipeIndicator) swipeIndicator = true;
      if (swipeDirection !== nextDirection) swipeDirection = nextDirection;
    } else {
      if (swipeIndicator) swipeIndicator = false;
    }
  }

  /**
   * @param {TouchEvent} e
   */
  function handleTouchEnd(e) {
    if (activeSource === "map") return;
    if (!swipeInProgress) return;

    const diffX = touchStartX - touchEndX;
    const diffY = Math.abs(touchStartY - touchEndY);

    if (Math.abs(diffX) > swipeThreshold && diffY < verticalThreshold) {
      if (diffX > 0) {
        setCondensedView(true);
        if (navigator.vibrate) navigator.vibrate(50);
      } else {
        setCondensedView(false);
        if (navigator.vibrate) navigator.vibrate(50);
      }
    }

    swipeInProgress = false;
    swipeIndicator = false;
  }

  function toggleView() {
    setCondensedView(!condensedView);
  }

  $: if (showEventCounters && !StatsPanelComponent) void ensureStatsPanelLoaded();
  $: if (condensedView && !PostTableComponent) void ensurePostTableLoaded();

  // Event handlers for components
  /**
   * @param {PostIdEvent} event
   */
  function handlePostLike(event) {
    likePost(event.detail.postId);
  }

  /**
   * @param {PostIdEvent} event
   */
  function handlePostToggleComments(event) {
    toggleComments(event.detail.postId);
  }

  /**
   * @param {PostShareEvent} event
   */
  function handlePostShare(event) {
    shareRequest = event.detail;
  }

  /**
   * @param {PostIdEvent} event
   */
  function handlePostToggleDescription(event) {
    toggleDescription(event.detail.postId);
  }

  /**
   * @param {{ postId: string, comment: string }} submission
   */
  function handleCommentSubmission(submission) {
    submitComment(submission.postId, submission.comment);
  }

  /**
   * @param {PostIdEvent} event
   */
  function handleTableToggleExpand(event) {
    toggleExpand(event.detail.postId);
  }

  /**
   * @param {PostIdEvent} event
   */
  function handleTableCloseComments(event) {
    const post = posts.find((p) => p.id === event.detail.postId);
    if (post && post.showComments) {
      posts = posts.map((p) =>
        p.id === event.detail.postId ? { ...p, showComments: false } : p,
      );
    }
  }

  onMount(() => {
    const prefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)",
    ).matches;
    const storedMode = localStorage.getItem("darkMode");
    const storedAccessibilityMode = localStorage.getItem(ACCESSIBILITY_MODE_STORAGE_KEY);
    darkMode = storedMode ? storedMode === "true" : prefersDark;
    accessibilityMode = storedAccessibilityMode === "true";
    applyUserPreferences();

    const connection = /** @type {Navigator & { connection?: { saveData?: boolean, effectiveType?: string } }} */ (navigator).connection;
    const shouldPreloadMap =
      !connection?.saveData && !["slow-2g", "2g"].includes(connection?.effectiveType || "");
    const mapPreloadTimer = shouldPreloadMap
      ? window.setTimeout(() => void preloadMapResources(), 2500)
      : 0;

    currentUsername =
      localStorage.getItem("username") || generateRandomUsername();
    if (!localStorage.getItem("username")) {
      localStorage.setItem("username", currentUsername);
    }

    window.addEventListener("online", updateOnlineStatus);
    window.addEventListener("offline", updateOnlineStatus);
    updateOnlineStatus();

    // Removed 60s fetchIncidents interval to prevent screen wiping

    window.addEventListener("scroll", debouncedHandleScroll, { passive: true });

    if (scrollContainer) {
      scrollContainer.addEventListener("touchstart", handleTouchStart, {
        passive: true,
      });
      scrollContainer.addEventListener("touchmove", handleTouchMove, {
        passive: true,
      });
      scrollContainer.addEventListener("touchend", handleTouchEnd, {
        passive: true,
      });
    }

    const refresh = () => {
      if (isOnline && !loading && !loadingMore && activeSource !== "map") {
        checkForUpdates();
        if (shouldFetchStats()) fetchIncidentStats();
      }
    };
    let updateInterval;
    const unsubscribeVisibility = pageVisible.subscribe((visible) => {
      document.body.classList.toggle("page-hidden", !visible);
      clearInterval(updateInterval);
      if (visible) {
        refresh();
        updateInterval = setInterval(refresh, 20000);
      } else {
        stopUpdateRequest();
        stopStatsRequest();
      }
    });

    return () => {
      clearInterval(updateInterval);
      unsubscribeVisibility();
      currentController?.abort();
      stopUpdateRequest();
      stopStatsRequest();
      debouncedHandleScroll.cancel();
      document.body.classList.remove("page-hidden");
      if (mapPreloadTimer) window.clearTimeout(mapPreloadTimer);
      window.removeEventListener("online", updateOnlineStatus);
      window.removeEventListener("offline", updateOnlineStatus);
      window.removeEventListener("scroll", debouncedHandleScroll);
      if (scrollContainer) {
        scrollContainer.removeEventListener("touchstart", handleTouchStart);
        scrollContainer.removeEventListener("touchmove", handleTouchMove);
        scrollContainer.removeEventListener("touchend", handleTouchEnd);
      }
    };
  });

  /**
   * @param {StringDetailEvent} event
   */
  function handleSourceChange(event) {
    setSourceFilter(event.detail);
  }

  /**
   * @param {StringDetailEvent} event
   */
  function handleStatsTimeFilter(event) {
    setTimeFilter(event.detail);
  }

  /**
   * @param {StringDetailEvent} event
   */
  function handleStatsTypeFilter(event) {
    filterByType(event.detail);
  }

  /**
   * @param {StringDetailEvent} event
   */
  function handleStatsLocationFilter(event) {
    filterByLocation(event.detail);
  }

  /**
   * @param {KeyboardEvent} event
   */
  function handleLoadMoreKeydown(event) {
    if (event.key === "Enter") {
      forceLoadMore();
    }
  }

  async function checkForUpdates() {
    if (updateController || document.hidden || !isOnline || activeSource === "map") return;
    const controller = new AbortController();
    updateController = controller;
    const requestId = currentRequestId;
    try {
      const url = buildIncidentsUrl({
        limit: postsPerPage,
        types: selectedTypes,
        locations: selectedLocations,
        activeOnly: showActiveOnly,
        source: activeSource,
      });
      const res = await fetch(url, { signal: controller.signal });
      if (!res.ok) return;
      const incidents = await res.json();
      if (controller.signal.aborted || requestId !== currentRequestId || !Array.isArray(incidents)) return;

      const result = reconcileIncidents(posts, incidents);
      if (result.posts === posts) return;
      clearAllClientCaches();
      posts = result.posts;
      for (const post of result.additions) {
        seenCompositeKeys.add(`${post.id}-${post.timestamp}-${post.location}`);
      }
      if (result.additions.length) {
        addToast(t("toast.newIncidents", { count: result.additions.length }), "info");
      }
    } catch (err) {
      if (!controller.signal.aborted) console.error("Error checking for updates:", err);
    } finally {
      if (updateController === controller) updateController = null;
    }
  }

</script>

<div class="container" bind:this={scrollContainer}>
  {#if import.meta.env.VITE_MOCK_DATA}
    <p class="mock-data-notice">Demo mode · Sample incidents, not live reports</p>
  {/if}
  {#if !accessibilityMode}
    <HeadlineTicker
      events={[
        ...posts.slice(0, 5),
        ...posts.filter(
          (p) =>
            p.active &&
            p.type &&
            p.type.toLowerCase().includes("sig") &&
            !posts.slice(0, 5).some((bp) => bp.id === p.id),
        ),
      ]}
    />
  {/if}
  <div class="header-surface">
    <Header
      {showEventCounters}
      {darkMode}
      {condensedView}
      accessibilityMode={accessibilityMode}
      {activeSource}
      on:toggleEventCounters={toggleEventCounters}
      on:toggleDarkMode={toggleDarkMode}
      on:toggleAccessibilityMode={toggleAccessibilityMode}
      on:toggleView={toggleView}
    />

    {#if activeSource !== "map"}
      <div
        id="incident-stats"
        class="stats-panel-shell"
        use:expandPanel={showEventCounters}
        class:expanded={showEventCounters}
        aria-hidden={!showEventCounters}
        inert={!showEventCounters}
      >
        <div class="stats-panel-content">
          {#if StatsPanelComponent}
            <svelte:component
              this={StatsPanelComponent}
              {eventsToday}
              {eventsLastHour}
              {eventsActive}
              {totalIncidents}
              {timeFilter}
              {hourlyData}
              {previousPeriodData}
              {historicalCurrentHourAverage}
              {historicalHourSampleCount}
              referenceTime={statsReferenceTime}
              {incidentsByType}
              {topLocations}
              {selectedTypes}
              {selectedLocations}
              on:filterTime={handleStatsTimeFilter}
              on:filterType={handleStatsTypeFilter}
              on:filterLocation={handleStatsLocationFilter}
              on:resetTypeFilters={resetTypeFilters}
              on:resetLocationFilters={resetLocationFilters}
            />
          {/if}
        </div>
      </div>
    {/if}
  </div>

  <div class="toolbar-row">
    <div class="toolbar">
      <div class="tabs-container">
        <SourceTabs
          {activeSource}
          on:changeSource={handleSourceChange}
        />
      </div>
      <div class="search-wrapper">
        <SearchBar
          bind:value={searchQuery}
          on:activate={() => activeSource === "map" && setSourceFilter("all")}
        />
      </div>
    </div>
    {#if activeSource !== "map"}
      <div class="toolbar-view-toggle">
        <ViewToggle
          {condensedView}
          {swipeIndicator}
          {swipeDirection}
          on:toggle={toggleView}
        />
      </div>
    {/if}
  </div>

  {#if activeSource === "map" && !MapTabComponent}
    <div class="map-loading">{t("state.loadingMap")}</div>
  {/if}

  <!-- Load the map tab lazily, then keep it mounted after the first open -->
  {#if MapTabComponent}
    <div style={activeSource === "map" ? "" : "display:none"}>
      <svelte:component this={MapTabComponent} isVisible={activeSource === "map"} />
    </div>
  {/if}

  {#if activeSource !== "map"}
    <section class="feed-region" aria-label="Incidents" aria-busy={loading} inert={loading && posts.length > 0}>
      {#if loading && !hasLoadedFeed}
        <div class="loading-container" in:fade={{ duration: 150 }}>
          {#each Array(6) as _}
            <SkeletonCard />
          {/each}
        </div>
      {:else if posts.length === 0}
        <div class="empty-state" in:fade={{ duration: 150 }}>
          <div class="empty-icon">📂</div>
          <p>{t("state.noIncidentsTitle")}</p>
          <p>{t("state.noIncidentsSubtitle")}</p>
        </div>
      {:else if displayPosts.length === 0}
        <div class="empty-state" in:fade={{ duration: 150 }}>
          <div class="empty-icon">🔍</div>
          <p>{t("state.noSearchTitle")}</p>
          <p>{t("state.noSearchSubtitle")}</p>
        </div>
      {:else if condensedView}
        {#if PostTableComponent}
          <svelte:component
            this={PostTableComponent}
            posts={displayPosts}
            {animateFeedEntrance}
            {searchQuery}
            {expandedPostId}
            on:toggleExpand={handleTableToggleExpand}
            on:closeComments={handleTableCloseComments}
            on:like={handlePostLike}
            on:toggleComments={handlePostToggleComments}
            on:share={handlePostShare}
            on:toggleDescription={handlePostToggleDescription}
            onSubmitComment={handleCommentSubmission}
            on:goToMap={() => setSourceFilter("map")}
          />
        {/if}
      {:else}
        <div class="feed" in:fade={{ duration: 200 }}>
          {#each displayPosts as post, i (post.compositeId)}
            <PostCard
              {post}
              index={i}
              {animateFeedEntrance}
              {postsPerPage}
              {searchQuery}
              suspendMiniMaps={suspendFeedMiniMaps}
              on:like={handlePostLike}
              on:toggleComments={handlePostToggleComments}
              on:share={handlePostShare}
              on:toggleDescription={handlePostToggleDescription}
              onSubmitComment={handleCommentSubmission}
              on:goToMap={() => setSourceFilter("map")}
            />
          {/each}
        </div>
      {/if}

    </section>

    {#if !allPostsLoaded && posts.length > 0 && posts.length >= postsPerPage}
      <div
        class="scroll-indicator"
        in:fade={{ duration: 150 }}
        on:click={forceLoadMore}
        role="button"
        tabindex="0"
        on:keydown={handleLoadMoreKeydown}
      >
        <div class="scroll-dots">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
        <p>{t("state.moreIncidentsAvailable")}</p>
      </div>
    {/if}
  {/if}

  <ToastContainer />
  {#if shareRequest}
    <ShareDialog
      post={shareRequest.post}
      elements={shareRequest.elements}
      onClose={() => (shareRequest = null)}
    />
  {/if}

  <footer class="app-footer" in:fade={{ delay: 400, duration: 200 }}>
    <div class="footer-content">
      <span class="footer-decorator">[</span>
      <p>
        Created and Developed by <a
          href="https://github.com/DuffyAdams"
          target="_blank"
          rel="noopener noreferrer">Duffy Adams</a
        >
      </p>
      <span class="footer-decorator">]</span>
    </div>
  </footer>
</div>

<style>
  .mock-data-notice {
    margin: 0;
    padding: 0.5rem 1rem;
    text-align: center;
    font-size: 0.85rem;
    color: var(--text-main);
    background: var(--bg-surface-elevated);
    border-bottom: 1px solid var(--border-color);
  }

  :global(html),
  :global(body) {
    margin: 0;
    padding: 0;
    width: 100%;
    max-width: 100%;
    position: relative;
  }

  :global(body) {
    font-family:
      "Inter",
      "Segoe UI",
      system-ui,
      -apple-system,
      sans-serif;
    transition:
      background-color 0.3s,
      color 0.3s;
    background-color: var(--bg-color);
    color: var(--text-color);
  }

  .container {
    max-width: 1440px;
    margin: 0 auto;
    padding: 1.25rem 1.5rem 2rem;
    box-sizing: border-box;
    width: 100%;
    position: relative;
    touch-action: pan-y;
  }

  .feed-region {
    position: relative;
  }

  .feed-region[aria-busy="true"]::before {
    content: "";
    position: absolute;
    top: -8px;
    inset-inline: 0;
    height: 2px;
    background: var(--accent-primary);
    border-radius: 999px;
  }

  .loading-container {
    display: flex;
    flex-wrap: wrap;
    gap: 1.25rem;
    justify-content: center;
    width: 100%;
    box-sizing: border-box;
  }

  .feed {
    display: flex;
    flex-wrap: wrap;
    gap: 1.25rem;
    justify-content: center;
    width: 100%;
    box-sizing: border-box;
  }

  .empty-state {
    text-align: center;
    max-width: 560px;
    margin: 2rem auto;
    padding: 4.5rem 2rem;
    color: var(--text-muted);
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-xl);
    corner-shape: squircle;
    box-shadow: var(--shadow-sm);
  }

  .header-surface {
    margin-top: 0.25rem;
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-xl);
    corner-shape: squircle;
    box-shadow: var(--shadow-md);
    overflow: clip;
  }

  .stats-panel-shell {
    height: 0;
    overflow: hidden;
    overflow-anchor: none;
    visibility: hidden;
    transition:
      height 420ms cubic-bezier(0.22, 1, 0.36, 1),
      visibility 420ms step-end;
  }

  .stats-panel-shell.expanded {
    visibility: visible;
    transition: height 420ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  .stats-panel-content {
    display: flow-root;
  }

  @media (max-width: 720px) {
    .header-surface {
      border-radius: var(--radius-lg);
    }
  }

  .empty-icon {
    font-size: 2.5rem;
    margin-bottom: 1rem;
    opacity: 0.75;
  }

  /* Scroll indicator */
  .scroll-indicator {
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    max-width: 360px;
    padding: 1rem 1.5rem;
    color: var(--text-muted);
    font-size: 0.9rem;
    opacity: 0.8;
    cursor: pointer;
    transition: all 0.2s ease;
    margin: 1.5rem auto;
    border: 1px solid var(--border-color);
    border-radius: 999px;
    background: var(--bg-surface);
    box-shadow: var(--shadow-sm);
  }

  .scroll-indicator:hover {
    opacity: 1;
    transform: translateY(-3px);
    border-color: color-mix(in srgb, var(--accent-primary) 45%, var(--border-color));
    box-shadow: var(--shadow-md);
  }

  .scroll-dots {
    display: flex;
    gap: 3px;
    margin-bottom: 6px;
  }

  .dot {
    width: 6px;
    height: 6px;
    background-color: var(--text-muted);
    border-radius: 50%;
    animation: bounce 1.4s infinite ease-in-out both;
  }

  .dot:nth-child(1) {
    animation-delay: -0.32s;
  }
  .dot:nth-child(2) {
    animation-delay: -0.16s;
  }

  @keyframes bounce {
    0%,
    80%,
    100% {
      transform: translateY(0);
    }
    40% {
      transform: translateY(-8px);
    }
  }

  /* Footer */
  .app-footer {
    text-align: center;
    margin-top: 2rem;
    padding: 2rem 0 1rem 0;
    color: var(--text-muted);
    font-size: 0.8rem;
    letter-spacing: -0.01em;
    border-top: 1px solid var(--border-color);
    display: flex;
    justify-content: center;
  }

  .footer-content {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-color);
    padding: 0.65rem 1.25rem;
    border-radius: 999px;
    box-shadow: var(--shadow-sm);
  }

  .footer-decorator {
    color: var(--accent-primary, var(--primary-color));
    font-weight: bold;
    opacity: 0.7;
  }

  .app-footer p {
    margin: 0;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .app-footer a {
    color: var(--accent-primary, var(--primary-color));
    text-decoration: none;
    font-weight: bold;
    position: relative;
    transition: all 0.2s ease;
  }

  .app-footer a::after {
    content: "";
    position: absolute;
    bottom: -2px;
    left: 0;
    width: 100%;
    height: 1px;
    background-color: var(--accent-primary, var(--primary-color));
    transform: scaleX(0);
    transform-origin: right;
    transition: transform 0.3s ease;
  }

  .app-footer a:hover {
    color: var(--primary-light);
  }

  .app-footer a:hover::after {
    transform: scaleX(1);
    transform-origin: left;
  }

  /* Mobile responsive */
  @media (max-width: 768px) {
    .container {
      padding: 0.75rem;
    }
    .feed,
    .loading-container {
      gap: 1rem;
      padding: 0;
    }
  }

  @media (max-width: 480px) {
    .feed,
    .loading-container {
      gap: 0.5rem;
    }

    .container {
      padding: 0.55rem;
    }

    @media (max-width: 360px) {
      .container {
        padding: 0.5rem;
      }
    }
  }
  
  /* Toolbar layout */
  .toolbar-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
    align-items: center;
    width: 100%;
    margin: 0.85rem 0 1.2rem;
  }

  .toolbar {
    display: flex;
    flex-direction: row;
    gap: 0;
    width: fit-content;
    max-width: 100%;
    box-sizing: border-box;
    grid-column: 2;
    margin: 0;
    align-items: center;
    position: relative;
    padding: 0.38rem;
    border: 1px solid var(--border-color);
    border-radius: 20px;
    corner-shape: squircle;
    background: var(--bg-surface);
    box-shadow: var(--shadow-md);
  }
  
  .tabs-container {
    width: auto;
    min-width: 0;
    flex: 0 1 auto;
    display: flex;
    justify-content: center;
    overflow: hidden;
  }

  .search-wrapper {
    width: auto;
    flex: 0 0 auto;
    margin-left: .35rem;
    padding-left: .35rem;
    border-left: 1px solid var(--border-color);
  }

  .toolbar-view-toggle {
    display: flex;
    align-items: center;
    flex: 0 0 auto;
    grid-column: 3;
    justify-self: end;
  }

  @media (max-width: 767px) {
    .toolbar-row {
      display: block;
      margin: 0.85rem 0 1.2rem;
    }

    .toolbar {
      width: 100%;
    }

    .tabs-container {
      flex: 1 1 auto;
    }

    .toolbar-view-toggle {
      height: 0;
    }
  }
</style>
