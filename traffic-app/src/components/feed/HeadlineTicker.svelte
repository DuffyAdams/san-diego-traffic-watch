<script>
    export let events = [];

    // Normalize headline text before it enters the scrolling feed ticker.
    function formatText(str) {
        if (!str) return "";
        return String(str)
            .replace(/[\r\n]+/g, " ")
            .replace(/\s+/g, " ")
            .trim();
    }
</script>

    <div class="ticker-wrapper" class:empty={events.length === 0} aria-hidden={events.length === 0}>
        <div class="ticker-label">
            <span class="blinking-dot"></span>
            LATEST
        </div>
        <!-- Keyboard users need to focus this scroll region in reduced-motion mode. -->
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
        <div class="ticker-content" tabindex={events.length ? 0 : -1} role="region" aria-label="Latest incidents">
            <div class="ticker-track">
                <div class="ticker-group">
                    {#each events as event}
                        <div
                            class="ticker-item"
                            class:sig-alert={event.type &&
                                event.type.toLowerCase().includes("sig")}
                        >
                            <span class="ticker-time">[{event.time}]</span>
                            <span class="ticker-type"
                                >{formatText(event.type).toUpperCase()}</span
                            >
                            <span class="ticker-desc">
                                {event.location
                                    ? formatText(event.location).toUpperCase()
                                    : "LOCATION PENDING"}
                            </span>
                        </div>
                    {/each}
                </div>
                <!-- Duplicate for infinite scroll -->
                <div class="ticker-group" aria-hidden="true">
                    {#each events as event}
                        <div
                            class="ticker-item"
                            class:sig-alert={event.type &&
                                event.type.toLowerCase().includes("sig")}
                        >
                            <span class="ticker-time">[{event.time}]</span>
                            <span class="ticker-type"
                                >{formatText(event.type).toUpperCase()}</span
                            >
                            <span class="ticker-desc">
                                {event.location
                                    ? formatText(event.location).toUpperCase()
                                    : "LOCATION PENDING"}
                            </span>
                        </div>
                    {/each}
                </div>
            </div>
        </div>
    </div>

<style>
    /* Empty sources keep the header and source tabs in the same position. */
    .ticker-wrapper.empty {
        visibility: hidden;
    }

    .ticker-wrapper {
        display: flex;
        align-items: center;
        background: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        corner-shape: squircle;
        margin-bottom: 0.8rem;
        overflow: hidden;
        height: 40px;
        box-shadow: var(--shadow-sm);
    }

    .ticker-label {
        flex: 0 0 auto;
        background: var(--primary-lightest);
        color: var(--accent-primary);
        padding: 0 1rem;
        height: 100%;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-weight: bold;
        font-size: 0.8rem;
        letter-spacing: 0.06em;
        white-space: nowrap;
        z-index: 2;
        position: relative;
        border-right: 1px solid var(--border-color);
    }

    .blinking-dot {
        width: 6px;
        height: 6px;
        background-color: var(--accent-primary);
        border-radius: 50%;
        animation: blink 1s infinite alternate;
    }

    @keyframes blink {
        0% {
            opacity: 0.3;
        }
        100% {
            opacity: 1;
        }
    }

    .ticker-content {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        position: relative;
        height: 100%;
        display: flex;
        align-items: center;
        mask-image: linear-gradient(
            to right,
            transparent,
            black 2%,
            black 98%,
            transparent
        );
        -webkit-mask-image: linear-gradient(
            to right,
            transparent,
            black 2%,
            black 98%,
            transparent
        );
    }

    .ticker-track {
        display: flex;
        width: max-content;
        min-width: 200%;
        flex-shrink: 0;
        animation: scroll 45s linear infinite;
    }

    /* Touch browsers retain :hover after a tap; never let that freeze news. */
    @media (hover: hover) and (pointer: fine) {
        .ticker-content:hover .ticker-track {
            animation-play-state: paused;
        }
    }

    .ticker-content:focus-visible .ticker-track {
        animation-play-state: paused;
    }

    .ticker-group {
        display: flex;
        flex: 1 0 auto;
        box-sizing: border-box;
        gap: 3rem;
        padding-right: 3rem;
    }

    .ticker-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        font-size: 0.8rem;
        letter-spacing: 0;
        white-space: nowrap;
        flex-shrink: 0;
    }

    .ticker-time {
        color: var(--text-muted, #a0aec0);
    }

    .sig-alert {
        background: rgba(255, 51, 51, 0.15);
        padding: 0.15rem 0.6rem;
        border-radius: 999px;
        border: 1px solid rgba(255, 51, 51, 0.3);
    }

    .sig-alert .ticker-time,
    .sig-alert .ticker-type,
    .sig-alert .ticker-desc {
        color: #ff4d4d !important;
        font-weight: 900 !important;
        text-shadow: none;
    }

    .ticker-type {
        color: var(--accent-color, #ed8936);
        font-weight: bold;
    }

    :global(.dark-mode) .ticker-type {
        color: #ff9900;
    }

    .ticker-desc {
        color: var(--text-main, #f8fafc);
    }

    @keyframes scroll {
        0% {
            transform: translateX(0);
        }
        100% {
            transform: translateX(-50%);
        }
    }

    @media (prefers-reduced-motion: reduce) {
        .ticker-content {
            overflow-x: auto;
            mask-image: none;
            -webkit-mask-image: none;
        }
        .ticker-track {
            animation: none;
            min-width: 100%;
        }
        .blinking-dot {
            animation: none;
        }
        .ticker-group[aria-hidden="true"] {
            display: none;
        }
    }

    @media (max-width: 768px) {
        .ticker-label {
            padding: 0 0.5rem;
            font-size: 0.7rem;
        }
        .ticker-item {
            font-size: 0.75rem;
        }
        .ticker-group {
            gap: 2rem;
            padding-right: 2rem;
        }
        .ticker-wrapper {
            margin-bottom: 0.75rem;
        }
    }
</style>
