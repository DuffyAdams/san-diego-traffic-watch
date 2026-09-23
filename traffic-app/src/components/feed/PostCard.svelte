<script>
    import { animateHeight } from "../../utils/animateHeight.js";
    import { createEventDispatcher } from "svelte";
    import { slide, revealUp } from "../../utils/motion.js";
    import CommentOverlay from "./CommentOverlay.svelte";
    import {
        truncateDescription,
        highlightFuzzy,
    } from "../../utils/helpers.js";
    import Zap from "lucide-svelte/icons/zap";
    import Clock from "lucide-svelte/icons/clock";
    import MapPin from "lucide-svelte/icons/map-pin";
    import Heart from "lucide-svelte/icons/heart";
    import MessageSquare from "lucide-svelte/icons/message-square";
    import Share2 from "lucide-svelte/icons/share-2";
    import Info from "lucide-svelte/icons/info";
    import X from "lucide-svelte/icons/x";
    import ChevronDown from "lucide-svelte/icons/chevron-down";
    import ChevronUp from "lucide-svelte/icons/chevron-up";
    import IncidentIcon from "../shared/IncidentIcon.svelte";
    import { mapPanTo } from "../../stores/appStore.js";
    import LazyImage from "../shared/LazyImage.svelte";
    import LiveTimestamp from "../shared/LiveTimestamp.svelte";
    import IncidentMiniMap from "../map/IncidentMiniMap.svelte";
    import { t } from "../../utils/i18n.js";

    export let post;
    export let index = 0;
    export let animateFeedEntrance = true;
    export let postsPerPage = 30;
    export let searchQuery = "";
    export let suspendMiniMaps = false;
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
        // Police
        "AUTO THEFT": "#3b82f6",
        "MISD HIT/RUN": "#ef4444",
        VANDALISM: "#8b5cf6",
        ROBBERY: "#1d4ed8",
        "SUICIDE-THREATS": "#9333ea",
        "DISTURBING PEACE": "#6366f1",
        "REPORT OF DEATH": "#000000",
        "PRISONER IN CUSTODY": "#374151",
        "MENTAL CASE": "#ec4899",
        // Fire
        MEDICAL: "#ef4444",
        "STRUCTURE FIRE": "#b91c1c",
        "VEGETATION FIRE": "#166534",
        "TRAFFIC ACCIDENT": "#f59e0b",
    };

    $: badgeColor = incidentColors[post.type] || "#fbbf24";
    $: isSigAlert = post.type === "SIG Alert";

    const severityConfig = {
        1: { label: "MINOR", color: "#64748b" },
        2: { label: "LOW", color: "#06b6d4" },
        3: { label: "MODERATE", color: "#eab308" },
        4: { label: "HIGH", color: "#f97316" },
        5: { label: "CRITICAL", color: "#ef4444" },
    };
    $: sevInfo = post.severity ? severityConfig[post.severity] : null;

    let showRawDetails = false;

    function toggleRawDetails() {
        showRawDetails = !showRawDetails;
    }

    function handleLike() {
        dispatch("like", { postId: post.id });
    }

    function handleToggleComments() {
        dispatch("toggleComments", { postId: post.id });
    }

    function handleShare(event) {
        dispatch("share", { post, elements: [event.currentTarget.closest(".post")] });
    }

    function handleToggleDescription() {
        dispatch("toggleDescription", { postId: post.id });
    }

    function handleCommentSubmit(comment) {
        onSubmitComment({
            postId: post.id,
            comment,
        });
    }

    function handleCommentClose() {
        dispatch("toggleComments", { postId: post.id });
    }

    function handleLocationClick(event) {
        event.stopPropagation();
        if (post.latitude != null && post.longitude != null) {
            mapPanTo.set({
                id: post.id,
                latitude: post.latitude,
                longitude: post.longitude,
            });
            dispatch("goToMap", { postId: post.id });
        }
    }
</script>

<div
    class="post"
    class:active={post.active}
    class:sig-alert={isSigAlert}
    in:slide={{
        delay: animateFeedEntrance ? Math.min((index % postsPerPage) * 25, 100) : 0,
        duration: animateFeedEntrance ? 280 : 0,
    }}
>
    <div class="post-content">
        <div class="post-image-container">
            <div
                class="post-badge"
                class:sig-alert-badge={isSigAlert}
                style="--badge-color: {badgeColor}"
            >
                <span class="incident-icon">
                    <IncidentIcon type={post.type} />
                </span>
                <span class="incident-type">{@html highlightFuzzy(post.type, searchQuery)}</span>
            </div>
            {#if post.active}
                <div class="active-badge">
                    <span class="active-icon"><Zap size={12} /></span>
                    <span>{t("status.active")}</span>
                </div>
            {/if}
            {#if post.details && post.details.length > 0}
                <button
                    class="raw-details-button"
                    aria-expanded={showRawDetails}
                    on:click={toggleRawDetails}
                    title={t("actions.viewRawDetails")}
                    aria-label={t("actions.viewRawDetails")}
                    type="button"
                >
                    <Info size={12} />
                    <span class="details-text">{t("actions.details")}</span>
                </button>
            {/if}
            <div
                class={`placeholder-container ${post.active ? "active" : ""}`}
                style="--bg-color: {badgeColor}"
            >
                {#if post.latitude != null && post.longitude != null}
                    <IncidentMiniMap
                        latitude={post.latitude}
                        longitude={post.longitude}
                        type={post.type}
                        active={post.active}
                        deferActivation={suspendMiniMaps}
                    />
                {:else if post.image && post.image !== "/maps/"}
                    <LazyImage
                        src={post.image}
                        alt="Incident location map"
                        className="post-image"
                        priority={index < 3}
                    />
                {:else}
                    <div class="placeholder-content">
                        <IncidentIcon type={post.type} size={48} />
                    </div>
                {/if}
            </div>
            {#if showRawDetails}
                <div
                    class="raw-details-inline-overlay"
                    transition:revealUp={{ duration: 280 }}
                >
                    <div class="raw-details-inline-header">
                        <h4>{t("actions.rawEventDetails")}</h4>
                        <button
                            class="close-inline-button"
                            on:click={() => (showRawDetails = false)}
                            aria-label="Close event details"
                            type="button"
                        >
                            <X size={16} />
                        </button>
                    </div>
                    <div class="raw-details-inline-content">
                        {#each post.details as detail}
                            <div class="detail-item">{detail}</div>
                        {/each}
                    </div>
                </div>
            {/if}
        </div>

        <div class="post-info">
            <div class="post-header">
                <span class="post-time">
                    <Clock size={14} />
                    <LiveTimestamp timestamp={post.timestamp} />
                </span>
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <span
                    class="post-location"
                    class:clickable-location={post.latitude != null &&
                        post.longitude != null}
                    on:click={handleLocationClick}
                >
                    <MapPin size={14} />
                    {@html highlightFuzzy(post.location, searchQuery)}
                </span>
            </div>
            <div
                class="post-description"
            >
                {#if sevInfo}
                    <div class="description-header">
                        <div
                            class="severity-inline-badge"
                            class:severity-critical={post.severity === 5}
                            style="--sev-color: {sevInfo.color}"
                        >
                            <span class="sev-score-box">{post.severity}</span>
                            <span class="sev-label"
                                >{sevInfo.label} SEVERITY</span
                            >
                        </div>
                    </div>
                {/if}
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
                                    on:click={handleToggleDescription}
                                    type="button"
                                    aria-expanded={!!post.showFullDescription}
                                    aria-label={t(post.showFullDescription ? "actions.collapseDescription" : "actions.expandDescription")}
                                    title={t(post.showFullDescription ? "actions.collapseDescription" : "actions.expandDescription")}
                                >
                                    {#if post.showFullDescription}
                                        <ChevronUp size={16} aria-hidden="true" />
                                    {:else}
                                        <ChevronDown size={16} aria-hidden="true" />
                                    {/if}
                                </button>
                            {/if}
                        {:else}
                            <span class="no-data">{t("fallback.noDataAvailable")}</span>
                        {/if}
                    </div>
                </div>
            </div>
            <div class="post-actions">
                <button
                    class="action-button like-button"
                    class:liked={post.likedByUser}
                    class:like-error={post.likeErrorAnimation}
                    on:click={handleLike}
                    type="button"
                    aria-label={`${t("actions.like")} (${post.likes})`}
                >
                    <span class="button-icon">
                        <Heart
                            size={18}
                            fill={post.likedByUser ? "currentColor" : "none"}
                        />
                    </span>
                    <span>{post.likes > 0 ? post.likes : t("actions.like")}</span>
                </button>
                <button
                    class="action-button comment-button"
                    on:click={handleToggleComments}
                    type="button"
                    aria-label={`${t("actions.comment")} (${post.comments.length})`}
                >
                    <span class="button-icon">
                        <MessageSquare size={18} />
                    </span>
                    <span>
                        {post.comments.length > 0
                            ? post.comments.length
                            : t("actions.comment")}
                    </span>
                </button>
                <button
                    class="action-button share-button"
                    on:click={handleShare}
                    type="button"
                    aria-label={t("actions.share")}
                >
                    <span class="button-icon">
                        <Share2 size={18} />
                    </span>
                    <span>{t("actions.share")}</span>
                </button>
            </div>

            {#if post.showComments}
                <CommentOverlay
                    comments={post.comments}
                    newComment={post.newComment}
                    commentError={post.commentError}
                    onClose={handleCommentClose}
                    onSubmit={handleCommentSubmit}
                />
            {/if}
        </div>
    </div>
</div>

<style>
    :global(.search-highlight) {
        background-color: color-mix(in srgb, var(--accent-primary) 40%, transparent);
        color: var(--text-main);
        padding: 0 0.15rem;
        border-radius: 3px;
        corner-shape: squircle;
        font-weight: 700;
        box-shadow: inset 0 0 0 1px var(--accent-primary);
    }

    .post {
        flex: 1 1 calc(33.333% - 1.25rem);
        min-width: 320px;
        max-width: 450px;
        box-sizing: border-box;
        background: var(--bg-surface);
        border-radius: var(--radius-lg);
        corner-shape: squircle;
        border: 1px solid var(--border-color);
        transition: transform .4s var(--ease-out), border-color .25s, box-shadow .35s;
        position: relative;
        display: flex;
        flex-direction: column;
        margin-bottom: 0.35rem;
        width: 100%;
        overflow: hidden;
        box-shadow: var(--shadow-sm);
    }

    .post:hover {
        border-color: color-mix(in srgb, var(--accent-primary) 32%, var(--border-color));
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
    }

    .post.active {
        position: relative;
    }

    .post.sig-alert {
        border-color: color-mix(in srgb, var(--accent-secondary) 45%, var(--border-color));
        background: var(--bg-surface);
    }

    .post.sig-alert:hover {
        border-color: color-mix(in srgb, var(--accent-secondary) 65%, var(--border-color));
        box-shadow: var(--shadow-md);
    }

    @keyframes retroPulse {
        0% {
            box-shadow:
                0 0 4px rgba(255, 51, 51, 0.2),
                inset 0 0 2px rgba(255, 51, 51, 0.1);
            border-color: rgba(255, 51, 51, 0.4);
        }
        100% {
            box-shadow:
                0 0 12px rgba(255, 51, 51, 0.6),
                inset 0 0 4px rgba(255, 51, 51, 0.3);
            border-color: var(--accent-secondary);
        }
    }

    .post-content {
        padding: 0;
        display: flex;
        flex-direction: column;
        height: 100%;
        position: relative;
    }

    .post-image-container {
        position: relative;
        width: 100%;
        height: 215px;
        overflow: hidden;
        border-bottom: 1px solid var(--border-color);
        background-color: #000;
        border-radius: var(--radius-lg) var(--radius-lg) 0 0;
        corner-shape: squircle;
        isolation: isolate;
    }

    .placeholder-container {
        width: 100%;
        height: 100%;
        position: relative;
        z-index: 0;
    }

    .placeholder-content {
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--secondary-bg);
        opacity: 0.8;
        color: var(--text-muted);
    }

    .post-badge {
        position: absolute;
        top: 0.8rem;
        left: 0.8rem;
        background: var(--bg-surface-elevated);
        color: var(--text-main);
        padding: 0.42rem 0.68rem;
        border-radius: 12px;
        corner-shape: squircle;
        border: 1px solid color-mix(in srgb, var(--badge-color) 62%, var(--border-color));
        text-transform: uppercase;
        font-size: 0.7rem;
        font-weight: 550;
        display: flex;
        align-items: center;
        gap: 0.4rem;
        z-index: 5;
        box-shadow: var(--shadow-sm);
    }

    .post-badge:hover {
        background: var(--bg-surface-elevated);
    }

    .post-badge.sig-alert-badge {
        border: 1px solid color-mix(in srgb, var(--badge-color) 70%, var(--border-color));
        box-shadow: var(--shadow-sm);
    }

    .post-badge.sig-alert-badge:hover {
        box-shadow: var(--shadow-md);
    }

    .active-badge {
        position: absolute;
        top: 0.8rem;
        right: 0.8rem;
        background: #dc2626;
        color: #fff;
        padding: 0.25rem 0.5rem;
        border-radius: 11px;
        corner-shape: squircle;
        text-transform: uppercase;
        font-size: 0.7rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 0.25rem;
        z-index: 5;
        border: 1px solid rgba(255, 255, 255, 0.24);
        box-shadow: 0 6px 18px rgba(220, 38, 38, 0.3);
        animation: badgePulse 2.4s ease-in-out infinite;
    }

    .description-header {
        margin-bottom: 0.75rem;
        display: flex;
        align-items: center;
    }

    .severity-inline-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        background: color-mix(in srgb, var(--sev-color) 12%, var(--bg-surface-elevated));
        border: 1px solid color-mix(in srgb, var(--sev-color) 40%, transparent);
        color: var(--sev-color);
        padding: 0.15rem 0.5rem 0.15rem 0.15rem;
        border-radius: 10px;
        corner-shape: squircle;
        text-transform: uppercase;
        font-size: 0.6rem;
        font-weight: bold;
    }

    .severity-inline-badge .sev-score-box {
        background: var(--sev-color);
        color: #000;
        width: 16px;
        height: 16px;
        border-radius: 7px;
        corner-shape: squircle;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.65rem;
        font-weight: 900;
        line-height: 1;
    }

    .severity-inline-badge .sev-label {
        letter-spacing: 0.05em;
    }

    .severity-inline-badge.severity-critical {
        animation: severityPulseInline 2s infinite alternate;
        border-color: var(--sev-color);
    }

    @keyframes severityPulseInline {
        0% {
            box-shadow: 0 0 4px
                color-mix(in srgb, var(--sev-color) 20%, transparent);
        }
        100% {
            box-shadow: 0 0 12px
                color-mix(in srgb, var(--sev-color) 60%, transparent);
        }
    }

    .raw-details-button {
        position: absolute;
        bottom: 0.6rem;
        left: 0.6rem;
        background-color: rgba(0, 0, 0, 0.65);
        color: white;
        border: none;
        border-radius: 10px;
        corner-shape: squircle;
        height: 30px;
        padding: 0 7px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        z-index: 2;
        box-shadow: 0 2px 6px #0003;
        transition:
            background-color 0.2s ease,
            transform 0.15s ease;
        font-size: 0.65rem;
        font-weight: 600;
    }

    .raw-details-button :global(svg) {
        flex-shrink: 0;
    }

    .raw-details-button .details-text {
        max-width: 0;
        opacity: 0;
        margin-left: 0;
        overflow: hidden;
        white-space: nowrap;
        transition:
            max-width 0.25s ease,
            opacity 0.2s ease,
            margin-left 0.25s ease;
    }

    .raw-details-button:hover {
        background-color: rgba(0, 0, 0, 0.85);
        transform: scale(1.05);
    }

    .raw-details-button:hover .details-text {
        max-width: 50px;
        opacity: 1;
        margin-left: 5px;
    }

    .raw-details-inline-overlay {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.92);
        display: flex;
        flex-direction: column;
        z-index: 10;
        border-radius: var(--radius-lg) var(--radius-lg) 0 0;
        corner-shape: squircle;
        overflow: hidden;
    }

    .raw-details-inline-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.75rem 1rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        flex-shrink: 0;
    }

    .raw-details-inline-header h4 {
        margin: 0;
        font-size: 0.9rem;
        font-weight: 600;
        color: white;
    }

    .close-inline-button {
        background: rgba(255, 255, 255, 0.1);
        border: none;
        color: white;
        cursor: pointer;
        padding: 0.3rem;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 10px;
        corner-shape: squircle;
        transition: all 0.2s;
    }

    .close-inline-button:hover {
        background-color: rgba(255, 255, 255, 0.2);
    }

    .raw-details-inline-content {
        padding: 0.75rem 1rem;
        overflow-y: auto;
        flex: 1;
    }

    .detail-item {
        padding: 0.5rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        font-size: 0.8rem;
        color: rgba(255, 255, 255, 0.9);
        line-height: 1.4;
    }

    .detail-item:last-child {
        border-bottom: none;
    }

    .incident-icon {
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .active-icon {
        display: flex;
        align-items: center;
    }

    :global(.post-image) {
        width: 100%;
        height: 100%;
        object-fit: cover;
        border-radius: var(--radius-lg) var(--radius-lg) 0 0;
        corner-shape: squircle;
        transition: transform .7s var(--ease-out);
    }

    .post:hover :global(.post-image) {
        transform: scale(1.035);
    }

    /* Keep this as a backup in case the global selector doesn't work */
    .post-image {
        width: 100%;
        height: 100%;
        object-fit: cover;
        border-radius: var(--radius-lg) var(--radius-lg) 0 0;
        corner-shape: squircle;
        transition: transform 0.3s ease;
    }

    .post:hover .post-image {
        transform: scale(1.05);
    }

    .post-info {
        padding: 1.15rem 1.15rem 4.8rem;
        flex-grow: 1;
        display: flex;
        flex-direction: column;
    }

    .post-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.9rem;
        font-size: 0.82rem;
        gap: .7rem;
    }

    .post-time {
        color: var(--text-muted);
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 0.3rem;
    }

    .post-location {
        display: flex;
        align-items: center;
        gap: 0.3rem;
        min-width: 0;
        text-align: right;
    }

    .clickable-location {
        cursor: pointer;
        color: var(--accent-primary);
        text-decoration: none;
        transition: all 0.2s;
    }

    .clickable-location:hover {
        color: var(--primary-light);
    }

    .post-description {
        font-size: 0.88rem;
        line-height: 1.55;
        margin-bottom: 1.25rem;
        color: var(--text-muted);
        position: relative;
        text-align: left;
        background: var(--bg-surface-elevated);
        padding: 0.9rem;
        border: 1px solid var(--border-color);
        border-radius: 14px;
        corner-shape: squircle;
    }

    .description-text {
        white-space: pre-wrap;
    }

    .no-data {
        color: var(--text-muted);
        opacity: 0.6;
        font-style: italic;
    }

    .more-button {
        background: transparent;
        border: none;
        color: var(--text-muted);
        width: 28px;
        height: 28px;
        padding: 0;
        margin-left: 0.25rem;
        margin-top: 0.25rem;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        transition: background-color 0.15s ease, color 0.15s ease;
        border-radius: 9px;
        corner-shape: squircle;
        vertical-align: middle;
    }

    .more-button:hover {
        background: var(--hover-bg);
        color: var(--text-main);
    }

    .post-actions {
        display: flex;
        justify-content: space-between;
        border-top: 1px solid var(--border-color);
        padding: 0.7rem 0.8rem;
        gap: 0.5rem;
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        background: var(--bg-surface);
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

    @keyframes heartbeat {
        0%,
        100% {
            transform: scale(1);
        }
        50% {
            transform: scale(1.3);
        }
    }

    @keyframes errorShake {
        0%,
        100% {
            transform: translateX(0);
        }
        10%,
        30%,
        50%,
        70%,
        90% {
            transform: translateX(-5px);
        }
        20%,
        40%,
        60%,
        80% {
            transform: translateX(5px);
        }
    }

    @keyframes badgePulse {
        0%,
        100% {
            box-shadow:
                0 6px 18px rgba(220, 38, 38, 0.3),
                0 0 0 0 rgba(239, 68, 68, 0.24);
        }
        50% {
            box-shadow:
                0 6px 20px rgba(220, 38, 38, 0.38),
                0 0 0 4px rgba(239, 68, 68, 0);
        }
    }

    /* Mobile responsive styles */
    @media (max-width: 768px) {
        .post {
            flex: 0 0 100%;
            max-width: 100%;
            margin: 0 0 0.8rem 0;
            border-radius: var(--radius-lg);
            corner-shape: squircle;
        }
        .post-image-container {
            border-radius: var(--radius-lg) var(--radius-lg) 0 0;
            corner-shape: squircle;
        }
        .post-info {
            padding: 1rem 1rem 4rem;
        }
        .post-description {
            font-size: 0.95rem;
            line-height: 1.4;
            margin-bottom: 0.8rem;
        }
    }

    @media (max-width: 480px) {
        .post {
            margin: 0 0 0.5rem 0;
            border-radius: var(--radius-lg);
            corner-shape: squircle;
        }
        .post-image-container {
            border-radius: var(--radius-lg) var(--radius-lg) 0 0;
            corner-shape: squircle;
        }
        .post-info {
            padding: 0.7rem 0.7rem 4rem;
        }
        .post-header {
            margin-bottom: 0.7rem;
        }
        .post-description {
            font-size: 0.9rem;
            line-height: 1.35;
            margin-bottom: 0.7rem;
        }
        .post-actions {
            gap: 0.2rem;
            padding: 0.7rem 0.7rem 1rem 0.7rem;
        }
        .action-button {
            padding: 0.4rem 0.2rem;
            font-size: 0.85rem;
            gap: 0.2rem;
            min-height: 44px;
        }
        .action-button span:last-child {
            min-width: 18px;
        }
    }

    @media (max-width: 320px) {
        .post {
            margin: 0 0 0.3rem 0;
            border-radius: var(--radius-lg);
            corner-shape: squircle;
            min-width: unset;
            max-width: 100%;
        }
        .post-image-container {
            border-radius: var(--radius-lg) var(--radius-lg) 0 0;
            corner-shape: squircle;
        }
        .post-info {
            padding: 0.5rem 0.5rem 4rem;
        }
        .post-actions {
            gap: 0.2rem;
            padding: 0.5rem 0.5rem 1rem 0.5rem;
        }
        .action-button {
            padding: 0.3rem 0.1rem;
            font-size: 0.8rem;
            min-height: 44px;
        }
    }
</style>
