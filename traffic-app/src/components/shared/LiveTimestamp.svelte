<script>
    import { liveClock } from "../../stores/pageActivity.js";
    import { formatTimestamp } from "../../utils/helpers.js";
    import { formatRelativeTimeFromNow, t } from "../../utils/i18n.js";

    export let timestamp;

    let relativeTime = "";
    let staticTime = "";

    $: staticTime = timestamp ? formatTimestamp(timestamp) : t("fallback.recent");
    $: relativeTime = formatRelativeTimeFromNow(timestamp, { style: "short", now: $liveClock });
</script>

<span class="timestamp-container" aria-label={`${staticTime} (${relativeTime})`}>
    <span class="main-time">{staticTime}</span>
    <span class="custom-tooltip">{relativeTime}</span>
</span>

<style>
    .timestamp-container {
        position: relative;
        display: inline-flex;
        cursor: help;
        align-items: center;
    }

    .custom-tooltip {
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%) translateY(-6px);
        background: var(--bg-surface-elevated, #1e293b);
        color: var(--accent-primary, #3b82f6);
        padding: 0.35rem 0.6rem;
        border-radius: 6px;
        corner-shape: squircle;
        font-family: var(--font-mono, monospace);
        font-size: 0.75rem;
        font-weight: 700;
        white-space: nowrap;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        opacity: 0;
        visibility: hidden;
        transition: all 0.2s var(--ease-out);
        border: 1px solid var(--accent-primary, #3b82f6);
        box-shadow:
            0 4px 12px rgba(0, 0, 0, 0.5),
            0 0 8px
                color-mix(
                    in srgb,
                    var(--accent-primary, #3b82f6) 40%,
                    transparent
                );
        z-index: 100;
        pointer-events: none;
    }

    .custom-tooltip::after {
        content: "";
        position: absolute;
        top: 98%;
        left: 50%;
        transform: translateX(-50%);
        border-width: 5px;
        border-style: solid;
        border-color: var(--accent-primary, #3b82f6) transparent transparent
            transparent;
    }

    .timestamp-container:hover .custom-tooltip {
        opacity: 1;
        visibility: visible;
        transform: translateX(-50%) translateY(-2px);
    }
</style>
