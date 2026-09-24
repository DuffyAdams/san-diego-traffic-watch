<script>
    import { createEventDispatcher, onMount, onDestroy } from "svelte";
    import BarChart3 from "lucide-svelte/icons/chart-no-axes-column-increasing";
    import Eye from "lucide-svelte/icons/eye";
    import LayoutGrid from "lucide-svelte/icons/layout-grid";
    import LayoutList from "lucide-svelte/icons/layout-list";
    import Moon from "lucide-svelte/icons/moon";
    import Sun from "lucide-svelte/icons/sun";
    import sirenLogo from "../../assets/siren-logo.svg";
    import { formatDateTime, t } from "../../utils/i18n.js";

    export let showEventCounters = false;
    export let darkMode = true;
    export let condensedView = false;
    export let accessibilityMode = false;
    export let activeSource = "CHP";

    const dispatch = createEventDispatcher();
    let currentTime = "";
    let timeInterval;

    function updateTime() {
        currentTime = formatDateTime(new Date(), {
            hour: "2-digit",
            minute: "2-digit",
            timeZoneName: "short",
        });
    }

    onMount(() => {
        updateTime();
        timeInterval = setInterval(updateTime, 30000);
    });

    onDestroy(() => {
        if (timeInterval) clearInterval(timeInterval);
    });
</script>

<header class="header">
    <div class="header-top">
        <div class="header-brand">
            <div class="brand-icon" aria-hidden="true">
                <img src={sirenLogo} alt="" />
            </div>
            <div class="brand-titles">
                <h1>{t("header.brandTitle")}</h1>
            </div>
        </div>

        <div class="header-controls">
            <div class="live-status" aria-label={t("header.feedStatus", { time: currentTime })}>
                <span class="status-indicator"><span></span></span>
                <div>
                    <strong>Live feed</strong>
                    <small>{currentTime}</small>
                </div>
            </div>
            <div class="header-toggle-group">
                {#if activeSource !== "map"}
                    <button
                        class="control-toggle mobile-view-toggle"
                        on:click={() => dispatch("toggleView")}
                        type="button"
                        aria-pressed={condensedView}
                        aria-label={condensedView
                            ? t("view.expandToCardView")
                            : t("view.condenseToTableView")}
                        title={condensedView
                            ? t("view.expandToCardView")
                            : t("view.condenseToTableView")}
                    >
                        {#if condensedView}
                            <LayoutGrid size={18} />
                        {:else}
                            <LayoutList size={18} />
                        {/if}
                    </button>
                {/if}
                <button
                    class="control-toggle"
                    class:is-active={accessibilityMode}
                    on:click={() => dispatch("toggleAccessibilityMode")}
                    type="button"
                    aria-pressed={accessibilityMode}
                    aria-label={accessibilityMode
                        ? t("header.disableAccessibilityMode")
                        : t("header.enableAccessibilityMode")}
                    title={accessibilityMode
                        ? t("header.disableAccessibilityMode")
                        : t("header.enableAccessibilityMode")}
                >
                    <Eye size={18} />
                </button>
                <button
                    class="control-toggle"
                    on:click={() => dispatch("toggleDarkMode")}
                    type="button"
                    aria-pressed={darkMode}
                    aria-label={darkMode
                        ? t("header.switchToLightMode")
                        : t("header.switchToDarkMode")}
                    title={darkMode
                        ? t("header.switchToLightMode")
                        : t("header.switchToDarkMode")}
                >
                    {#if darkMode}<Sun size={18} />{:else}<Moon size={18} />{/if}
                </button>
                {#if activeSource !== "map"}
                    <button
                        class="control-toggle"
                        class:is-active={showEventCounters}
                        on:click={() => dispatch("toggleEventCounters")}
                        type="button"
                        aria-expanded={showEventCounters}
                        aria-controls="incident-stats"
                        aria-label={t("header.systemDiagnostics")}
                        title={t("header.systemDiagnostics")}
                    >
                        <BarChart3 size={18} />
                    </button>
                {/if}
            </div>
        </div>
    </div>

</header>

<style>
    .header {
        display: flex;
        flex-direction: column;
    }

    .header-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        padding: 0.62rem 0.75rem;
    }

    .header-brand,
    .header-controls,
    .header-toggle-group,
    .live-status {
        display: flex;
        align-items: center;
    }

    .header-brand { gap: 0.62rem; min-width: 0; }

    .brand-icon {
        width: 40px;
        height: 40px;
        display: grid;
        place-items: center;
        flex: 0 0 auto;
    }

    .brand-icon img {
        width: 31px;
        height: 31px;
        display: block;
        object-fit: contain;
    }

    .brand-titles h1 {
        margin: 0;
        color: var(--text-main);
        font-size: clamp(1.25rem, 2.3vw, 1.62rem);
        font-weight: 760;
        letter-spacing: -0.038em;
        line-height: 1;
    }

    .header-controls { gap: 0.72rem; flex: 0 0 auto; }

    .live-status {
        gap: 0.48rem;
        padding-right: 0.72rem;
        border-right: 1px solid var(--border-color);
    }

    .live-status > div { display: flex; align-items: baseline; gap: .35rem; }
    .live-status strong { font-size: 0.74rem; font-weight: 700; }
    .live-status small { color: var(--text-muted); font-size: 0.68rem; }

    .status-indicator {
        width: 18px;
        height: 18px;
        display: grid;
        place-items: center;
        border-radius: 50%;
        background: rgba(75, 215, 139, 0.13);
    }

    .status-indicator span {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--accent-success);
        box-shadow: 0 0 0 4px rgba(75, 215, 139, 0.1);
        animation: breathe 2.4s ease-in-out infinite;
    }

    .header-toggle-group { gap: 0.38rem; }

    .control-toggle {
        width: 36px;
        height: 36px;
        display: grid;
        place-items: center;
        padding: 0;
        color: var(--text-muted);
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        corner-shape: squircle;
        box-shadow: var(--shadow-sm);
        cursor: pointer;
        transition: transform .25s var(--ease-out), color .2s, border-color .2s, background .2s;
    }

    .control-toggle:hover,
    .control-toggle.is-active {
        color: var(--accent-primary);
        border-color: color-mix(in srgb, var(--accent-primary) 45%, var(--border-color));
        background: var(--primary-lightest);
    }

    .control-toggle:active { transform: scale(.96); }

    .mobile-view-toggle { display: none; }

    @keyframes breathe {
        50% { transform: scale(.82); opacity: .72; }
    }

    @media (max-width: 720px) {
        .header-top { padding: .58rem .65rem; }
        .live-status { display: none; }
        .header-controls { gap: .5rem; }
    }

    @media (max-width: 768px) {
        .mobile-view-toggle { display: grid; }
    }

    @media (max-width: 440px) {
        .header-top { gap: .5rem; }
        .header-brand { gap: .4rem; }
        .brand-icon { width: 30px; height: 30px; }
        .brand-titles h1 { font-size: 1.05rem; line-height: 1.15; }
        .control-toggle { width: 32px; height: 34px; border-radius: 11px; corner-shape: squircle; }
        .header-toggle-group { gap: .25rem; }
    }
</style>
