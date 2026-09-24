<script>
    import { animateHeight } from "../../utils/animateHeight.js";
    import { createEventDispatcher } from "svelte";
    import { slide } from "../../utils/motion.js";
    import {
        formatTimeOnly,
        truncateDescription,
        highlightFuzzy,
    } from "../../utils/helpers.js";
    import CommentOverlay from "./CommentOverlay.svelte";
    import Zap from "lucide-svelte/icons/zap";
    import Heart from "lucide-svelte/icons/heart";
    import MessageSquare from "lucide-svelte/icons/message-square";
    import Share2 from "lucide-svelte/icons/share-2";
    import ChevronDown from "lucide-svelte/icons/chevron-down";
    import IncidentIcon from "../shared/IncidentIcon.svelte";
    import LazyImage from "../shared/LazyImage.svelte";
    import IncidentMiniMap from "../map/IncidentMiniMap.svelte";
    import { mapPanTo } from "../../stores/appStore.js";
    import { t } from "../../utils/i18n.js";

    export let posts = [];
    export let animateFeedEntrance = true;
    export let expandedPostId = null;
    export let searchQuery = "";
    export let onSubmitComment = () => {};

    const dispatch = createEventDispatcher();

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
        "Live or Dead Animal": "#a78bfa",
        "Animal Hazard": "#a78bfa",
        "Defective Traffic Signals": "#eab308",
        JUMPER: "#8b5cf6",
        SPINOUT: "#06b6d4",
        "Wrong Way Driver": "#ec4899",
        "SIG Alert": "#dc2626",
        "Aircraft Emergency": "#3b82f6",
        "Provide Traffic Control": "#6366f1",
        "Assist CT with Maintenance": "#8b5cf6",
        Maintenance: "#6b7280",
        "Request CalTrans Notify": "#64748b",
        "Road Conditions": "#84cc16",
        "Traffic Break": "#0ea5e9",
    };

    function handleRowClick(post) {
        // If closing the currently expanded row and its comments are open, close comments first
        if (expandedPostId === post.id && post.showComments) {
            dispatch("closeComments", { postId: post.id });
        }
        dispatch("toggleExpand", { postId: post.id });
    }

    function handleLike(e, postId) {
        e.stopPropagation();
        dispatch("like", { postId });
    }

    function handleToggleComments(e, postId) {
        e.stopPropagation();
        dispatch("toggleComments", { postId });
    }

    function handleShare(e, post) {
        e.stopPropagation();
        const details = e.currentTarget.closest(".expanded-details");
        dispatch("share", { post, elements: [details.previousElementSibling, details] });
    }

    function handleToggleDescription(e, postId) {
        e.stopPropagation();
        dispatch("toggleDescription", { postId });
    }

    function handleCommentSubmit(postId, comment) {
        onSubmitComment({ postId, comment });
    }

    function handleCommentClose(postId) {
        dispatch("toggleComments", { postId });
    }

    function handleLocationClick(e, post) {
        if (post.latitude != null && post.longitude != null) {
            e.stopPropagation();
            mapPanTo.set({
                id: post.id,
                latitude: post.latitude,
                longitude: post.longitude,
            });
            dispatch("goToMap", { postId: post.id });
        }
    }
</script>

<div class="incidents-table">
    <div class="table-header">
        <div class="table-cell type-cell">{t("table.type")}</div>
        <div class="table-cell time-cell">{t("table.time")}</div>
        <div class="table-cell location-cell">{t("table.location")}</div>
        <div class="table-cell status-cell">{t("table.status")}</div>
    </div>

    {#each posts as post, i (post.compositeId)}
        <div
            class="table-row"
            class:active={post.active}
            class:expanded={expandedPostId === post.id}
            role="button"
            tabindex="0"
            on:click={() => handleRowClick(post)}
            on:keydown={(e) =>
                (e.key === "Enter" || e.key === " ") && handleRowClick(post)}
            in:slide={{ delay: animateFeedEntrance ? Math.min(i * 15, 90) : 0, duration: animateFeedEntrance ? 180 : 0 }}
        >
            <div class="table-cell type-cell">
                <span
                    class="incident-icon-small"
                    style="color: {incidentColors[post.type] || '#fbbf24'}"
                >
                    <IncidentIcon type={post.type} />
                </span>
                <span class="incident-type-small">{@html highlightFuzzy(post.type, searchQuery)}</span>
            </div>
            <div class="table-cell time-cell">
                <span class="full-time">{post.time}</span>
                <span class="mobile-time">{formatTimeOnly(post.timestamp)}</span
                >
            </div>
            <div
                class="table-cell location-cell"
                class:clickable-location={post.latitude != null &&
                    post.longitude != null}
                on:click={(e) => handleLocationClick(e, post)}
                role="button"
                tabindex="0"
                on:keydown={(e) =>
                    (e.key === "Enter" || e.key === " ") &&
                    handleLocationClick(e, post)}
            >
                {@html highlightFuzzy(post.location, searchQuery)}
            </div>
            <div class="table-cell status-cell">
                {#if post.active}
                    <span class="status-badge active"
                        ><Zap size={10} fill="currentColor" /> {t("status.active")}</span
                    >
                {:else}
                    <span class="status-badge">{t("status.inactive")}</span>
                {/if}
            </div>
            <span class="row-arrow"><ChevronDown size={16} /></span>
        </div>

        {#if expandedPostId === post.id}
            <div class="expanded-details" transition:slide={{ duration: 200 }}>
                <div class="expanded-content">
                    <div class="expanded-image">
                        {#if post.latitude != null && post.longitude != null}
                            <IncidentMiniMap
                                latitude={post.latitude}
                                longitude={post.longitude}
                                type={post.type}
                                active={post.active}
                            />
                        {:else}
                            <LazyImage
                                src={post.image}
                                alt="Incident location map"
                                className=""
                                priority={i < 3}
                            />
                        {/if}
                    </div>
                    <div class="expanded-info">
                        <div class="post-description">
                            <div use:animateHeight>
                                <div style="display: flow-root;">
                                    {#if post.description}
                                        <span class="description-text">
                                            {@html post.showFullDescription
                                                ? highlightFuzzy(post.description, searchQuery)
                                                : highlightFuzzy(truncateDescription(post.description), searchQuery)}
                                        </span>
                                        {#if post.description.length > 200}
                                            <button
                                                class="more-button"
                                                on:click={(e) =>
                                                    handleToggleDescription(e, post.id)}
                                                type="button"
                                                aria-expanded={!!post.showFullDescription}
                                                aria-label={t(post.showFullDescription ? "actions.collapseDescription" : "actions.expandDescription")}
                                                title={t(post.showFullDescription ? "actions.collapseDescription" : "actions.expandDescription")}
                                            >
                                                {post.showFullDescription
                                                    ? "[-]"
                                                    : "[+]"}
                                            </button>
                                        {/if}
                                    {:else}
                                        <span class="no-data">{t("fallback.noDataAvailable")}</span>
                                    {/if}
                                </div>
                            </div>
                        </div>
                        <div class="expanded-actions">
                            <button
                                class="action-button like-button"
                                class:liked={post.likedByUser}
                                class:like-error={post.likeErrorAnimation}
                                on:click={(e) => handleLike(e, post.id)}
                                type="button"
                                aria-label={`${t("actions.like")} (${post.likes})`}
                            >
                                <span class="button-icon">
                                    <Heart
                                        size={18}
                                        fill={post.likedByUser
                                            ? "currentColor"
                                            : "none"}
                                    />
                                </span>
                                <span
                                    >{post.likes > 0
                                        ? post.likes
                                        : t("actions.like")}</span
                                >
                            </button>
                            <button
                                class="action-button comment-button"
                                on:click={(e) =>
                                    handleToggleComments(e, post.id)}
                                type="button"
                                aria-label={`${t("actions.comment")} (${post.comments.length})`}
                            >
                                <span class="button-icon">
                                    <MessageSquare size={18} />
                                </span>
                                <span
                                    >{post.comments.length > 0
                                        ? post.comments.length
                                        : t("actions.comment")}</span
                                >
                            </button>
                            <button
                                class="action-button share-button"
                                on:click={(e) => handleShare(e, post)}
                                type="button"
                                aria-label={t("actions.share")}
                            >
                                <span class="button-icon">
                                    <Share2 size={18} />
                                </span>
                                <span>{t("actions.share")}</span>
                            </button>
                        </div>
                    </div>
                </div>

                {#if post.showComments}
                    <CommentOverlay
                        comments={post.comments}
                        newComment={post.newComment}
                        commentError={post.commentError}
                        onClose={() => handleCommentClose(post.id)}
                        onSubmit={(comment) =>
                            handleCommentSubmit(post.id, comment)}
                    />
                {/if}
            </div>
        {/if}
    {/each}
</div>

<style>
    .incidents-table {
        width: 100%;
        min-width: 100%;
        background: var(--bg-surface);
        border-radius: var(--radius-lg);
        corner-shape: squircle;
        border: 1px solid var(--border-color);
        overflow: hidden;
        margin-bottom: 1.5rem;
        box-sizing: border-box;
        max-width: 100%;
        box-shadow: var(--shadow-md);
    }

    .table-header {
        display: flex;
        background: var(--bg-surface-elevated);
        color: var(--text-muted);
        font-weight: 700;
        padding: 0.9rem 1rem;
        border-bottom: 1px solid var(--border-color);
        width: 100%;
        box-sizing: border-box;
    }

    .table-row {
        display: flex;
        padding: 0.72rem 0.65rem;
        border-bottom: 1px solid var(--border-color);
        background-color: var(--bg-surface);
        cursor: pointer;
        transition: background .2s, border-color .2s;
        position: relative;
        width: 100%;
        box-sizing: border-box;
    }

    .table-row:hover {
        background-color: var(--primary-lightest);
        z-index: 1;
    }

    .table-row.active {
        border-left: 4px solid var(--accent-secondary);
        background-color: rgba(255, 51, 102, 0.05);
    }

    .table-row.expanded {
        background-color: var(--bg-surface-elevated);
        border-bottom: none;
        box-shadow: 0 2px 8px var(--shadow-color);
    }

    .table-row .row-arrow {
        color: var(--text-muted);
        transition: transform 0.2s ease;
        display: flex;
        align-items: center;
        margin-left: auto;
    }

    .table-row.expanded .row-arrow {
        transform: rotate(180deg);
    }

    .table-cell {
        padding: 0.2rem 0.5rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .type-cell {
        flex: 0 0 18%;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .time-cell {
        flex: 0 0 22%;
    }

    .location-cell {
        flex: 1;
    }

    .location-cell.clickable-location {
        cursor: pointer;
        color: var(--accent-primary);
        text-decoration: none;
        transition: all 0.2s;
    }

    .location-cell.clickable-location:hover {
        color: var(--primary-light);
    }

    .status-cell {
        flex: 0 0 12%;
        text-align: center;
    }

    .incident-icon-small {
        font-size: 1rem;
        display: inline-block;
        margin-right: 0.3rem;
    }

    .incident-type-small {
        font-weight: 500;
    }

    .status-badge {
        display: inline-block;
        padding: 0.2rem 0.5rem;
        border-radius: 999px;
        font-size: 0.75rem;
        text-transform: uppercase;
        background-color: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        color: var(--text-muted);
    }

    .status-badge.active {
        background-color: rgba(220, 38, 38, 0.14);
        border-color: #dc2626;
        color: #ef4444;
        animation: badgePulse 2.4s ease-in-out infinite;
    }

    .expanded-details {
        background-color: var(--bg-surface-elevated);
        padding: 0 1rem 1rem 1rem;
        border-bottom: 1px solid var(--border-color);
        overflow: hidden;
        width: 100%;
        box-sizing: border-box;
        position: relative;
    }

    .expanded-content {
        display: flex;
        gap: 1rem;
        align-items: center;
    }

    .expanded-image {
        flex: 0 0 30%;
        max-width: 300px;
        height: 200px;
        border-radius: 18px;
        corner-shape: squircle;
        overflow: hidden;
    }

    .expanded-image :global(img) {
        width: 100%;
        height: 200px;
        object-fit: cover;
        border-radius: 18px;
        corner-shape: squircle;
    }

    .expanded-info {
        flex: 1;
        display: flex;
        flex-direction: column;
    }

    .expanded-actions {
        display: flex;
        justify-content: center;
        gap: 0.5rem;
        margin-top: 1rem;
    }

    .post-description {
        font-size: 0.85rem;
        line-height: 1.6;
        margin-bottom: 1.25rem;
        color: var(--text-muted);
        position: relative;
        text-align: left;
        background: var(--bg-surface-elevated);
        padding: 0.85rem;
        border: 1px solid var(--border-color);
        border-radius: 14px;
        corner-shape: squircle;
    }

    .description-text {
        display: block;
        white-space: pre-wrap;
    }

    .no-data {
        color: var(--text-muted);
        opacity: 0.6;
        font-style: italic;
    }

    .more-button {
        background: rgba(51, 102, 255, 0.05);
        border: 1px solid var(--accent-primary);
        color: var(--accent-primary);
        padding: 0.2rem 0.5rem;
        margin-left: auto;
        margin-top: 0.25rem;
        font-size: 0.7rem;
        font-weight: bold;
        cursor: pointer;
        display: flex;
        justify-content: center;
        min-width: 44px;
        min-height: 44px;
        align-items: center;
        transition: all 0.15s ease;
        text-transform: uppercase;
        border-radius: 9px;
        corner-shape: squircle;
        vertical-align: middle;
    }

    .more-button:hover {
        background: var(--accent-primary);
        color: #000;
        box-shadow: 0 0 8px rgba(51, 102, 255, 0.4);
    }

    .action-button {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.3rem;
        min-height: 42px;
        background: transparent;
        border: 1px solid transparent;
        color: var(--text-muted);
        font-size: 0.78rem;
        font-weight: 500;
        padding: 0.45rem 0;
        border-radius: 12px;
        corner-shape: squircle;
        cursor: pointer;
        transition: all 0.15s;
        flex: 1;
        max-width: calc(100% / 3);
    }

    .action-button:hover {
        background: var(--primary-lightest);
        border-color: color-mix(in srgb, var(--accent-primary) 22%, transparent);
        color: var(--accent-primary);
    }

    .like-button.liked {
        color: var(--accent-secondary);
        border-color: var(--accent-secondary);
        background-color: rgba(255, 51, 51, 0.15);
    }

    .like-button.liked .button-icon {
        display: inline-flex;
        animation: like-confirm 260ms var(--ease-out);
    }

    @keyframes like-confirm {
        from { transform: translateY(3px); }
        to { transform: translateY(0); }
    }

    .like-button.liked:hover {
        background-color: rgba(255, 51, 51, 0.25);
    }

    .button-icon {
        font-size: 1.1rem;
    }

    .like-button.like-error {
        color: var(--accent-secondary);
        animation: errorShake 0.4s;
        background-color: rgba(229, 62, 62, 0.1);
    }

    @keyframes errorShake {
        0%,
        100% {
            transform: translateX(0);
        }
        25% {
            transform: translateX(-5px);
        }
        75% {
            transform: translateX(5px);
        }
    }

    .full-time {
        display: inline;
    }

    .mobile-time {
        display: none;
    }

    @keyframes badgePulse {
        0%,
        100% {
            box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.2);
        }
        50% {
            box-shadow: 0 0 0 4px rgba(239, 68, 68, 0);
        }
    }

    @media (max-width: 768px) {
        .expanded-content {
            flex-direction: column;
        }
        .expanded-image {
            max-width: 100%;
            width: 100%;
            margin-bottom: 1rem;
            padding-top: 0.5rem;
        }
        .type-cell {
            flex: 0 0 25%;
        }
        .time-cell {
            flex: 0 0 25%;
        }
        .status-cell {
            flex: 0 0 20%;
        }
    }

    @media (max-width: 480px) {
        .full-time {
            display: none;
        }
        .mobile-time {
            display: inline;
        }
        .table-header {
            padding: 0.7rem 0.5rem;
        }
        .table-row {
            padding: 0.4rem 0.5rem;
        }
        .table-cell {
            padding: 0.1rem 0.2rem;
            font-size: 0.85rem;
        }
        .incident-type-small {
            display: none;
        }
        .type-cell {
            flex: 0 0 10%;
            justify-content: center;
        }
        .time-cell {
            flex: 0 0 30%;
        }
        .status-cell {
            flex: 0 0 20%;
        }
        .status-badge {
            display: none;
        }
        .table-header .status-cell {
            display: none;
        }
    }
</style>
