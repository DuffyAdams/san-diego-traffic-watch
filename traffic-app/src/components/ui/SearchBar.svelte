<script>
    import Search from "lucide-svelte/icons/search";
    import X from "lucide-svelte/icons/x";
    import { createEventDispatcher, flushSync } from "svelte";
    import { t } from "../../utils/i18n.js";

    export let value = "";
    export let placeholder = t("search.placeholder");
    export let expanded = false;

    const dispatch = createEventDispatcher();
    let inputRef;
    let toggleRef;

    function handleInput(e) {
        value = e.target.value;
        dispatch("input", value);
    }

    function clearSearch() {
        value = "";
        dispatch("input", value);
        inputRef?.focus();
    }

    function openSearch() {
        // Keep focus inside the touch gesture so mobile keyboards open first tap.
        flushSync(() => { expanded = true; });
        dispatch("activate");
        inputRef?.focus();
    }

    function closeSearch() {
        flushSync(() => { expanded = false; });
        toggleRef?.focus();
    }
</script>

<div class="search-container" class:expanded class:has-value={value.length > 0}>
    <button
        bind:this={toggleRef}
        class="search-toggle"
        type="button"
        aria-label={t("search.ariaLabel")}
        aria-expanded={expanded}
        on:click={openSearch}
    >
        <Search size={17} />
    </button>
    <div class="search-field" inert={!expanded}>
        <input
            bind:this={inputRef}
            type="search"
            class="search-input"
            aria-label={t("search.ariaLabel")}
            {placeholder}
            {value}
            on:input={handleInput}
            on:keydown={(event) => {
                if (event.key === "Escape") {
                    event.preventDefault();
                    closeSearch();
                }
            }}
        />
        {#if value.length > 0}
            <button class="clear-button" type="button" on:click={clearSearch} aria-label={t("search.clear")}>
                <X size={16} />
            </button>
        {/if}
        <button class="close-button" type="button" on:click={closeSearch} aria-label="Close search">Done</button>
    </div>
</div>

<style>
    .search-container {
        display: flex;
        align-items: center;
        width: 44px;
        height: 44px;
        box-sizing: border-box;
        overflow: hidden;
        border-radius: 13px;
        background: transparent;
        transition: width .24s ease, background .2s;
    }
    .search-container.expanded {
        width: 280px;
        background: var(--bg-surface-elevated);
        box-shadow: inset 0 0 0 1px var(--border-focus);
    }
    .search-toggle, .clear-button, .close-button {
        width: 44px;
        height: 44px;
        flex: 0 0 44px;
        padding: 0;
        border: 0;
        border-radius: 12px;
        background: transparent;
        color: var(--text-muted, #a0aec0);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
    }
    .search-container.has-value .search-toggle,
    .search-container.expanded .search-toggle { color: var(--accent-primary, #3182ce); }
    .search-field {
        min-width: 0;
        flex: 1;
        display: flex;
        align-items: center;
        visibility: hidden;
        opacity: 0;
        transition: opacity .18s ease;
    }
    .expanded .search-field { visibility: visible; opacity: 1; }
    .search-input {
        flex: 1;
        background: transparent;
        border: none;
        color: var(--text-main, #f8fafc);
        font-size: 16px;
        outline: none;
        min-width: 0;
        width: 100%;
    }
    .search-input::-webkit-search-cancel-button { display: none; }
    .search-input::placeholder { color: var(--text-muted, #a0aec0); }
    .close-button { font-size: 12px; color: var(--text-main); }
    button:focus-visible { outline: 2px solid var(--accent-primary); outline-offset: -3px; }
    @media (max-width: 650px) {
        .search-container, .search-container.expanded { width: 100%; }
    }
    @media (prefers-reduced-motion: reduce) {
        .search-container, .search-field { transition: none; }
    }
</style>
