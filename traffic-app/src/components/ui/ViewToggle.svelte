<script>
    import { fade } from "../../utils/motion.js";
    import ChevronLeft from "lucide-svelte/icons/chevron-left";
    import ChevronRight from "lucide-svelte/icons/chevron-right";
    import LayoutGrid from "lucide-svelte/icons/layout-grid";
    import LayoutList from "lucide-svelte/icons/layout-list";
    import { createEventDispatcher } from "svelte";
    import { t } from "../../utils/i18n.js";

    export let condensedView = false;
    export let swipeIndicator = false;
    export let swipeDirection = "";

    const dispatch = createEventDispatcher();

    function selectView(nextCondensedView) {
        if (nextCondensedView !== condensedView) dispatch("toggle");
    }
</script>

{#if swipeIndicator}
    <div class="swipe-indicator {swipeDirection}" in:fade={{ duration: 150 }}>
        <div class="swipe-content">
            <span class="swipe-icon">
                {#if swipeDirection === "left"}
                    <ChevronLeft size={32} />
                {:else}
                    <ChevronRight size={32} />
                {/if}
            </span>
            <span class="swipe-label">
                {swipeDirection === "left" ? t("view.tableView") : t("view.cardView")}
            </span>
            <span class="swipe-icon-secondary">
                {#if swipeDirection === "left"}
                    <LayoutList size={20} />
                {:else}
                    <LayoutGrid size={20} />
                {/if}
            </span>
        </div>
    </div>
{/if}

<div class="view-toggle" role="group" aria-label="Incident display mode">
    <button
        class:active={!condensedView}
        type="button"
        on:click={() => selectView(false)}
        aria-pressed={!condensedView}
        aria-label={t("view.expandToCardView")}
    >
        <LayoutGrid size={15} strokeWidth={1.8} />
        <span>{t("view.cards")}</span>
    </button>
    <button
        class:active={condensedView}
        type="button"
        on:click={() => selectView(true)}
        aria-pressed={condensedView}
        aria-label={t("view.condenseToTableView")}
    >
        <LayoutList size={15} strokeWidth={1.8} />
        <span>{t("view.table")}</span>
    </button>
</div>

<style>
    .swipe-indicator {
        position: fixed;
        top: 50%;
        transform: translateY(-50%);
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        color: var(--text-main);
        padding: 0;
        border-radius: 24px;
        corner-shape: squircle;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        z-index: 100;
        pointer-events: none;
        box-shadow: var(--shadow-md);
        width: 120px;
        height: 100px;
        text-align: center;
        opacity: 1;
    }

    .swipe-indicator.left {
        right: 20px;
        animation: slideInRight 0.3s var(--ease-out) forwards;
    }

    .swipe-indicator.right {
        left: 20px;
        animation: slideInLeft 0.3s var(--ease-out) forwards;
    }

    .swipe-content {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.5rem;
        height: 100%;
        justify-content: center;
    }

    .swipe-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        color: rgba(255, 255, 255, 0.95);
    }

    .swipe-label {
        font-size: 0.85rem;
        font-family: var(--font-mono);
        font-weight: normal;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        color: var(--accent-primary);
    }

    .swipe-icon-secondary {
        display: flex;
        align-items: center;
        justify-content: center;
        color: rgba(255, 255, 255, 0.5);
        margin-top: -0.25rem;
    }

    .view-toggle {
        display: inline-grid;
        grid-template-columns: repeat(2, auto);
        gap: 0.2rem;
        padding: 0.25rem;
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        border-radius: 14px;
        corner-shape: squircle;
        box-shadow: var(--shadow-sm);
    }

    .view-toggle button {
        min-height: 34px;
        padding: 0.38rem 0.7rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.38rem;
        border: 1px solid transparent;
        border-radius: 10px;
        corner-shape: squircle;
        background: transparent;
        color: var(--text-muted);
        font: inherit;
        font-size: 0.75rem;
        font-weight: 500;
        cursor: pointer;
        transition: color .2s ease, background .2s ease, border-color .2s ease, box-shadow .2s ease;
    }

    .view-toggle button:hover:not(.active) {
        color: var(--text-main);
        background: var(--primary-lightest);
    }

    .view-toggle button.active {
        color: var(--accent-primary);
        background: var(--bg-surface);
        border-color: color-mix(in srgb, var(--accent-primary) 30%, var(--border-color));
        box-shadow: 0 2px 8px rgba(0,0,0,.1);
    }

    .view-toggle button:focus-visible {
        outline: 2px solid var(--accent-primary);
        outline-offset: 2px;
    }

    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translate(16px, -50%);
        }
        to {
            opacity: 0.95;
            transform: translate(0, -50%);
        }
    }

    @keyframes slideInLeft {
        from {
            opacity: 0;
            transform: translate(-16px, -50%);
        }
        to {
            opacity: 0.95;
            transform: translate(0, -50%);
        }
    }

    @media (max-width: 768px) {
        .swipe-indicator {
            width: 100px;
            height: 84px;
        }

        .view-toggle button {
            padding-inline: 0.58rem;
        }

        .view-toggle {
            display: none;
        }
    }
</style>
