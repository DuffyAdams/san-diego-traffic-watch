<script>
    import { createEventDispatcher } from "svelte";
    import CarFront from "lucide-svelte/icons/car-front";
    import Flame from "lucide-svelte/icons/flame";
    import Map from "lucide-svelte/icons/map";
    import Shield from "lucide-svelte/icons/shield";
    import Siren from "lucide-svelte/icons/siren";
    import { t } from "../../utils/i18n.js";

    const dispatch = createEventDispatcher();
    export let activeSource = "CHP";

    const tabs = [
        { value: "CHP", label: t("filters.traffic"), icon: CarFront },
        { value: "SDPD", label: t("filters.sdpd"), icon: Siren },
        { value: "SDSO", label: t("filters.sheriff"), icon: Shield },
        { value: "SDFD", label: t("filters.fire"), icon: Flame },
        { value: "map", label: t("filters.map"), icon: Map },
    ];
</script>

<nav class="source-tabs" aria-label="Incident sources">
    {#each tabs as tab}
        <button
            class="source-tab"
            class:active={activeSource === tab.value}
            type="button"
            aria-pressed={activeSource === tab.value}
            aria-label={tab.label}
            on:click={() => dispatch("changeSource", tab.value)}
        >
            <svelte:component this={tab.icon} size={15} strokeWidth={2.2} />
            <span>{tab.label}</span>
        </button>
    {/each}
</nav>

<style>
    .source-tabs {
        display: flex;
        align-items: center;
        gap: 0.3rem;
        width: 100%;
        overflow-x: auto;
        scrollbar-width: none;
    }

    .source-tabs::-webkit-scrollbar { display: none; }

    .source-tab {
        min-height: 40px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.42rem;
        flex: 0 0 auto;
        padding: 0.55rem 0.78rem;
        color: var(--text-muted);
        white-space: nowrap;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 13px;
        corner-shape: squircle;
        font-size: 0.8rem;
        font-weight: 550;
        cursor: pointer;
        transition: color .2s, background .2s, border-color .2s, transform .25s var(--ease-out);
    }

    .source-tab:hover {
        color: var(--text-main);
        background: var(--hover-bg);
    }

    .source-tab.active {
        color: var(--text-main);
        background: var(--bg-surface-elevated);
        border-color: var(--border-color);
        box-shadow: var(--shadow-sm);
    }

    .source-tab:active { transform: scale(.97); }
    .source-tab :global(svg) { transition: color 180ms ease; }
    .source-tab.active :global(svg) {
        color: var(--accent-primary);
        animation: select-source 240ms var(--ease-out);
    }

    @keyframes select-source {
        from { transform: translateY(3px); }
        to { transform: translateY(0); }
    }

    @media (max-width: 650px) {
        .source-tabs {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            align-items: stretch;
            gap: 0;
            overflow: visible;
        }
        .source-tab {
            min-width: 0;
            min-height: 44px;
            flex-direction: column;
            gap: .25rem;
            padding: .5rem .125rem;
            white-space: normal;
            overflow-wrap: anywhere;
        }
        .source-tab span { max-width: 100%; }
        .source-tab :global(svg) { flex-shrink: 0; }
    }
</style>
