<script>
    import { slide } from "../../utils/motion.js";
    import { toasts, removeToast } from "../../stores/appStore.js";
</script>

{#if $toasts.length > 0}
    <div class="toast-container" role="status" aria-live="polite">
        {#each $toasts as toast (toast.id)}
            <div
                class="toast toast-{toast.type}"
                in:slide={{ duration: 280 }}
                out:slide={{ duration: 200 }}
            >
                <span class="toast-message">{toast.message}</span>
                <button
                    class="toast-close" type="button" aria-label="Dismiss notification"
                    on:click={() => removeToast(toast.id)}>×</button
                >
            </div>
        {/each}
    </div>
{/if}

<style>
    .toast-container {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 1000;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        max-width: 400px;
    }

    .toast {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1rem 1.25rem;
        border-radius: var(--radius-md);
        corner-shape: squircle;
        font-size: 0.9rem;
        text-transform: uppercase;
        font-weight: bold;
        background: var(--bg-surface-elevated);
        border: 1px solid var(--border-color);
        box-shadow: var(--shadow-md);
        min-width: 300px;
    }

    .toast-info {
        color: var(--accent-primary);
    }

    :global(body.dark-mode) .toast-info {
        color: var(--accent-primary);
    }

    .toast-success {
        color: var(--success-color, #00cc66);
    }

    :global(body.dark-mode) .toast-success {
        color: var(--success-color, #00cc66);
    }

    .toast-warning {
        color: var(--accent-warning, #ffcc00);
    }

    :global(body.dark-mode) .toast-warning {
        color: var(--accent-warning, #ffcc00);
    }

    .toast-error {
        color: var(--accent-secondary, #ff3333);
    }

    :global(body.dark-mode) .toast-error {
        color: var(--accent-secondary, #ff3333);
    }

    .toast-message {
        flex: 1;
        line-height: 1.4;
    }

    .toast-close {
        background: none;
        border: none;
        color: inherit;
        font-size: 1.2rem;
        cursor: pointer;
        padding: 0;
        margin-left: 0.5rem;
        opacity: 0.8;
        transition: opacity 0.2s;
        line-height: 1;
    }

    .toast-close:hover {
        opacity: 1;
    }

    @media (max-width: 480px) {
        .toast-container {
            left: 20px;
            right: 20px;
            top: 20px;
            max-width: none;
        }

        .toast {
            min-width: auto;
            max-width: 100%;
            font-size: 0.85rem;
            padding: 0.75rem 1rem;
        }
    }
</style>
