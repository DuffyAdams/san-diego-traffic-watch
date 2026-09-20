<script>
    import Search from "lucide-svelte/icons/search";
    import X from "lucide-svelte/icons/x";
    import { createEventDispatcher } from "svelte";
    import { t } from "../../utils/i18n.js";
    import { slide } from "../../utils/motion.js";

    export let value = "";
    export let placeholder = t("search.placeholder");

    const dispatch = createEventDispatcher();
    let inputRef;
    let containerRef;
    let expanded = false;

    function handleInput(e) {
        value = e.target.value;
        dispatch("input", value);
    }

    function clearSearch() {
        value = "";
        dispatch("input", value);
        if (inputRef) inputRef.focus();
    }

    function openSearch() {
        expanded = true;
        dispatch("activate");
        requestAnimationFrame(() => inputRef?.focus());
    }

    function handleFocusOut() {
        requestAnimationFrame(() => {
            if (!containerRef?.contains(document.activeElement) && !value) {
                expanded = false;
            }
        });
    }
</script>

<div
    bind:this={containerRef}
    class="search-container"
    class:expanded
    class:has-value={value.length > 0}
    on:focusout={handleFocusOut}
>
    <button
        class="search-toggle"
        type="button"
        aria-label={t("search.ariaLabel")}
        aria-expanded={expanded || value.length > 0}
        on:click={openSearch}
    >
        <Search size={15} />
    </button>
    <div class="search-field">
        <input
            bind:this={inputRef}
            type="search"
            class="search-input"
            aria-label={t("search.ariaLabel")}
            {placeholder}
            {value}
            on:focus={() => (expanded = true)}
            on:input={handleInput}
        />
        {#if value.length > 0}
            <button class="clear-button" type="button" on:click={clearSearch} aria-label={t("search.clear")} in:slide={{ axis: "x", duration: 180 }}>
                <X size={14} />
            </button>
        {/if}
    </div>
</div>

<style>
    .search-container {
        display: flex;
        align-items: center;
        width: 42px;
        height: 42px;
        box-sizing: border-box;
        overflow: hidden;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 13px;
        corner-shape: squircle;
        padding: 0;
        margin: 0;
        transition: width .28s var(--ease-out), border-color .2s, box-shadow .2s, background .2s;
        box-shadow: none;
        position: relative;
    }

    .search-container.expanded,
    .search-container.has-value,
    .search-container:focus-within {
        width: min(240px, 58vw);
        background: var(--bg-surface-elevated);
        border-color: var(--border-focus);
        box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent-primary) 13%, transparent);
    }

    .search-toggle {
        width: 40px;
        height: 40px;
        flex: 0 0 40px;
        padding: 0;
        border: 0;
        border-radius: 12px;
        corner-shape: squircle;
        background: transparent;
        color: var(--text-muted, #a0aec0);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: color .2s, background .2s;
    }

    .search-toggle:hover {
        color: var(--text-main);
    }

    .search-container:focus-within .search-toggle,
    .search-container.expanded .search-toggle {
        color: var(--accent-primary, #3182ce);
    }

    .search-field {
        min-width: 0;
        flex: 1;
        display: flex;
        align-items: center;
        padding-right: .45rem;
        opacity: 0;
        transform: translateX(-4px);
        pointer-events: none;
        transition: opacity .16s ease, transform .22s var(--ease-out);
    }

    .search-container.expanded .search-field,
    .search-container.has-value .search-field,
    .search-container:focus-within .search-field {
        opacity: 1;
        transform: translateX(0);
        pointer-events: auto;
    }

    .search-input {
        flex: 1;
        background: transparent;
        border: none;
        color: var(--text-main, #f8fafc);
        font-size: 0.84rem;
        outline: none;
        min-width: 0;
        width: 100%;
    }

    .search-input::placeholder {
        color: var(--text-muted, #a0aec0);
        opacity: 0.6;
    }

    .clear-button {
        background: transparent;
        border: none;
        color: var(--text-muted, #a0aec0);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0.25rem;
        border-radius: 9px;
        corner-shape: squircle;
        transition: all 0.2s ease;
        margin-left: 0.5rem;
        flex: 0 0 auto;
    }

    .clear-button:hover {
        background: rgba(255, 255, 255, 0.1);
        color: var(--text-main, #f8fafc);
    }

    :global(body:not(.dark-mode)) .clear-button:hover {
        background: rgba(0, 0, 0, 0.05);
        color: #1a202c;
    }

    :global(body:not(.dark-mode)) .search-input { color: var(--text-main); }

    @media (hover: hover) and (pointer: fine) {
        .search-container:hover {
            width: min(240px, 58vw);
            border-color: var(--border-color);
        }

        .search-container:hover .search-field {
            opacity: 1;
            transform: translateX(0);
            pointer-events: auto;
        }
    }

    @media (prefers-reduced-motion: reduce) {
        .search-container,
        .search-field { transition: none; }
    }
</style>
