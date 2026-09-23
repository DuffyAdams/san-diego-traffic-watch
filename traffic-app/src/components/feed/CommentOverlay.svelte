<script>
    import { slide } from "../../utils/motion.js";
    import { formatCommentTimestamp } from "../../utils/helpers.js";
    import { t } from "../../utils/i18n.js";
    import X from "lucide-svelte/icons/x";
    import User from "lucide-svelte/icons/user";
    import MessageSquare from "lucide-svelte/icons/message-square";
    import Send from "lucide-svelte/icons/send";

    export let comments = [];
    export let newComment = "";
    export let commentError = "";
    export let onClose = () => {};
    export let onSubmit = () => {};

    function handleClose() {
        onClose();
    }

    function handleSubmit() {
        if (!newComment.trim()) return;
        onSubmit(newComment.trim());
        newComment = "";
    }

    function handleKeyPress(e) {
        if (e.key === "Enter") {
            handleSubmit();
        }
    }
</script>

<div
    class="comments-overlay"
    in:slide={{ duration: 280 }}
    out:slide={{ duration: 200 }}
>
    <button class="close-comments" type="button" on:click={handleClose} aria-label={t("actions.closeComments")}>
        <X size={18} aria-hidden="true" />
    </button>
    <h3 class="comments-title">
        <MessageSquare size={18} />
        {t("comments.title", { count: comments.length })}
    </h3>

    {#if commentError}
        <p class="error-message">{commentError}</p>
    {/if}

    <div class="comments-container">
        {#if comments.length === 0}
            <p class="no-comments">{t("comments.empty")}</p>
        {:else}
            {#each comments as comment, i}
                <div class="comment" style="animation-delay: {i * 20}ms">
                    <div class="comment-header">
                        <div class="comment-avatar">
                            <User size={14} />
                        </div>
                        <div class="comment-user-info">
                            <span class="comment-username"
                                >{comment.username}</span
                            >
                            <span class="comment-timestamp"
                                >{formatCommentTimestamp(
                                    comment.timestamp,
                                )}</span
                            >
                        </div>
                    </div>
                    <div class="comment-content">
                        {comment.comment}
                    </div>
                </div>
            {/each}
        {/if}
    </div>

    <div class="add-comment">
        <input
            type="text"
            bind:value={newComment}
            aria-label={t("comments.placeholder")}
            placeholder={t("comments.placeholder")}
            maxlength="150"
            on:keypress={handleKeyPress}
        />
        <button type="button" on:click={handleSubmit}>
            <Send size={14} />
            {t("actions.send")}
        </button>
    </div>
</div>

<style>
    .comments-overlay {
        position: absolute;
        bottom: 0;
        left: 0;
        width: 100%;
        height: calc(100% - 50px);
        background: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-bottom: none;
        display: flex;
        flex-direction: column;
        padding: 1.2rem;
        z-index: 10;
        border-radius: 20px 20px 0 0;
        corner-shape: squircle;
        box-sizing: border-box;
        backface-visibility: hidden;
    }

    .close-comments {
        position: absolute;
        top: 0.8rem;
        right: 0.8rem;
        background: transparent;
        color: var(--text-muted);
        border: none;
        font-size: 1rem;
        line-height: 1;
        cursor: pointer;
        z-index: 11;
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 10px;
        corner-shape: squircle;
        padding: 0;
        transition: background-color 0.15s ease, color 0.15s ease;
    }

    .close-comments:hover {
        background: var(--hover-bg);
        color: var(--text-main);
    }

    .comments-title {
        font-size: 1.1rem;
        color: var(--text-main);
        font-weight: 720;
        margin: 0 0 0.8rem 0;
        padding-right: 2rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .comments-container {
        flex: 1;
        overflow-y: auto;
        padding-right: 0.6rem;
        margin: 0.3rem 0;
        max-height: calc(100% - 90px);
    }

    .comments-container::-webkit-scrollbar {
        width: 4px;
    }

    .comments-container::-webkit-scrollbar-track {
        background: var(--border-color);
        border-radius: 0;
    }

    .comments-container::-webkit-scrollbar-thumb {
        background: var(--accent-primary);
        border-radius: 0;
    }

    .no-comments {
        color: var(--text-muted);
        text-align: center;
        padding: 1rem 0;
        background-color: var(--bg-surface-elevated);
        border-radius: 14px;
        corner-shape: squircle;
        opacity: 0.8;
        border: 1px solid var(--border-color);
    }

    .comment {
        display: flex;
        flex-direction: column;
        margin-bottom: 0.8rem;
        animation: fadeIn 150ms ease-in forwards;
        opacity: 0;
    }

    .comment-header {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        margin-bottom: 0.2rem;
        padding-left: 0.1rem;
    }

    .comment-avatar {
        width: 24px;
        height: 24px;
        background: var(--bg-surface-elevated);
        color: var(--accent-primary);
        border-radius: 9px;
        corner-shape: squircle;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        font-size: 0.75rem;
        border: 1px solid var(--border-color);
    }

    .comment-user-info {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .comment-username {
        color: var(--text-main);
        font-size: 0.8rem;
        white-space: nowrap;
    }

    .comment-timestamp {
        font-size: 0.7rem;
        color: var(--text-muted);
        position: relative;
        padding-left: 0.5rem;
    }

    .comment-timestamp::before {
        content: "\2022";
        position: absolute;
        left: 0;
        color: var(--text-muted);
        opacity: 0.5;
    }

    .comment-content {
        background-color: rgba(51, 102, 255, 0.05);
        padding: 0.6rem 0.8rem;
        border-radius: 4px 14px 14px 14px;
        corner-shape: squircle;
        border: 1px solid var(--border-color);
        font-size: 0.9rem;
        line-height: 1.4;
        color: var(--text-main);
        margin-left: 2rem;
        word-break: break-word;
        position: relative;
    }

    .add-comment {
        display: flex;
        gap: 0.5rem;
        margin-top: 0.8rem;
    }

    .add-comment input {
        flex: 1;
        padding: 0.7rem 1rem;
        border: 1px solid var(--border-color);
        border-radius: 13px;
        corner-shape: squircle;
        font-size: 0.9rem;
        background-color: var(--bg-surface-elevated);
        color: var(--text-main);
        transition: all 0.15s;
    }

    .add-comment input:focus {
        outline: none;
        border-color: var(--accent-primary);
        box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent-primary) 12%, transparent);
    }

    .add-comment input::placeholder {
        color: var(--text-muted);
    }

    .add-comment button {
        background: var(--accent-primary);
        color: var(--text-inverse);
        border: 1px solid transparent;
        border-radius: 13px;
        corner-shape: squircle;
        padding: 0.7rem 1.2rem;
        font-size: 0.9rem;
        cursor: pointer;
        transition: all 0.15s;
        outline: none;
    }

    .add-comment button:hover {
        background: var(--primary-light);
        transform: translateY(-1px);
    }

    .error-message {
        color: var(--accent-secondary);
        background-color: rgba(255, 51, 51, 0.1);
        border-left: 2px solid var(--accent-secondary);
        padding: 0.6rem 1rem;
        margin-top: 0.6rem;
        font-size: 0.85rem;
        border-radius: 12px;
        corner-shape: squircle;
    }

    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(5px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
</style>
