<script>
    import { onMount } from "svelte";
    import X from "lucide-svelte/icons/x";
    import { createShareImage } from "../../utils/shareImage.js";
    import { t } from "../../utils/i18n.js";

    export let post;
    export let elements;
    export let onClose;

    let dialog;
    let file;
    let previewUrl = "";
    let loading = true;
    let sharing = false;
    let error = "";
    const url = window.location.origin;
    $: text = t("share.incidentSummary", {
        description: post.description,
        location: post.location,
    });

    onMount(() => {
        const previousFocus = document.activeElement;
        let disposed = false;
        dialog.showModal();
        createShareImage(elements, post.id).then((image) => {
            if (disposed) return;
            file = image;
            previewUrl = URL.createObjectURL(file);
        }).catch(() => {
            if (!disposed) error = t("share.imageFailed");
        }).finally(() => {
            if (!disposed) loading = false;
        });
        return () => {
            disposed = true;
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            dialog.close();
            if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus();
        };
    });

    async function share() {
        if (sharing) return;
        sharing = true;
        error = "";
        try {
            if (navigator.share) {
                await navigator.share({ title: t("app.name"), text, url });
            } else {
                const twitterUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;
                window.open(twitterUrl, "_blank", "noopener,noreferrer");
            }
            onClose();
        } catch (cause) {
            if (cause.name !== "AbortError") error = t("share.shareFailed");
        } finally {
            sharing = false;
        }
    }

</script>

<dialog bind:this={dialog} aria-labelledby="share-title" on:close={onClose}>
    <div class="share-header">
        <h2 id="share-title">{t("share.title")}</h2>
        <button class="close-button" on:click={onClose} aria-label={t("share.close")} type="button"><X size={20} /></button>
    </div>
    {#if loading}
        <p role="status">{t("share.preparing")}</p>
    {:else if previewUrl}
        <img class="share-preview" src={previewUrl} alt={t("share.previewAlt", { location: post.location })} />
    {/if}
    {#if error}<p role="alert">{error}</p>{/if}
    <div class="share-actions">
        {#if previewUrl}<a href={previewUrl} download={file.name}>{t("share.download")}</a>{/if}
        <button class="primary" on:click={share} disabled={sharing} type="button">{t("actions.share")}</button>
    </div>
</dialog>

<style>
    dialog {
        width: min(480px, calc(100vw - 32px));
        max-height: calc(100dvh - 32px);
        box-sizing: border-box;
        padding: 20px;
        border: 1px solid var(--border-color);
        border-radius: var(--radius-lg);
        color: var(--text-main);
        background: var(--bg-surface);
        box-shadow: var(--shadow-md);
        overflow: auto;
    }
    dialog::backdrop { background: rgba(7, 9, 13, 0.78); }
    .share-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; }
    h2 { margin: 0; font-size: 1.15rem; }
    p { color: var(--text-muted); font-size: 0.9rem; line-height: 1.5; }
    p[role="alert"] { color: var(--error-color); }
    .share-preview { display: block; width: 100%; max-height: 60dvh; object-fit: contain; border-radius: 12px; }
    .share-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
    button, a { display: inline-flex; align-items: center; justify-content: center; min-height: 44px; padding: 10px 14px; box-sizing: border-box; border: 0; border-radius: 12px; background: var(--bg-surface-elevated); color: var(--text-main); font: inherit; font-size: 0.9rem; text-decoration: none; cursor: pointer; }
    .primary { background: var(--accent-primary); color: var(--text-inverse); }
    .close-button { padding: 10px; }
    button:disabled { opacity: 0.6; cursor: wait; }
    button:focus-visible, a:focus-visible { outline: 2px solid var(--accent-primary); outline-offset: 2px; }
</style>
