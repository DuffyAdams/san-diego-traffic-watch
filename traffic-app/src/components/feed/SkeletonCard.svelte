<script>
    // Loading placeholder that matches the feed card dimensions.
</script>

<div class="skeleton-card">
    <div class="skeleton-image"></div>
    <div class="skeleton-content">
        <div class="skeleton-header">
            <div class="skeleton-time"></div>
            <div class="skeleton-location"></div>
        </div>
        <div class="skeleton-description"></div>
        <div class="skeleton-actions">
            <div class="skeleton-button"></div>
            <div class="skeleton-button"></div>
            <div class="skeleton-button"></div>
        </div>
    </div>
</div>

<style>
    .skeleton-card {
        background: var(--card-bg);
        border-radius: var(--radius-lg);
        corner-shape: squircle;
        box-shadow:
            0 4px 20px var(--shadow-color),
            0 0 0 1px rgba(0, 0, 0, 0.03);
        overflow: hidden;
        box-shadow: var(--shadow-sm);
        animation: skeleton-pulse 1.5s ease-in-out infinite;
        flex: 0 0 calc(33.333% - 1.5rem);
        min-width: 300px;
        max-width: 400px;
        box-sizing: border-box;
        margin-bottom: 2rem;
    }

    .skeleton-image {
        height: 200px;
        background: linear-gradient(
            90deg,
            var(--border-color) 25%,
            transparent 50%,
            var(--border-color) 75%
        );
        background-size: 200% 100%;
        animation: skeleton-shimmer 1.5s infinite;
    }

    .skeleton-content {
        padding: 1.4rem;
    }

    .skeleton-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }

    .skeleton-time {
        width: 35%;
        height: 14px;
        background: var(--border-color);
        border-radius: 6px;
        corner-shape: squircle;
    }

    .skeleton-location {
        width: 40%;
        height: 14px;
        background: var(--border-color);
        border-radius: 6px;
        corner-shape: squircle;
    }

    .skeleton-description {
        width: 100%;
        height: 48px;
        background: var(--border-color);
        border-radius: 6px;
        corner-shape: squircle;
        margin-bottom: 1.2rem;
    }

    .skeleton-actions {
        display: flex;
        justify-content: space-between;
        border-top: 1px solid var(--border-color);
        padding-top: 0.7rem;
        gap: 0.3rem;
    }

    .skeleton-button {
        flex: 1;
        height: 32px;
        background: var(--border-color);
        border-radius: 6px;
        corner-shape: squircle;
    }

    @keyframes skeleton-pulse {
        0%,
        100% {
            opacity: 1;
        }
        50% {
            opacity: 0.7;
        }
    }

    @keyframes skeleton-shimmer {
        0% {
            background-position: -200% 0;
        }
        100% {
            background-position: 200% 0;
        }
    }

    /* Mobile styles */
    @media (max-width: 768px) {
        .skeleton-card {
            flex: 0 0 100%;
            max-width: 100%;
            margin: 0 0 0.8rem 0;
            border-radius: 6px;
            corner-shape: squircle;
        }
        .skeleton-image {
            border-radius: 6px 6px 0 0;
            corner-shape: squircle;
        }
        .skeleton-content {
            padding: 1rem 1rem 0.6rem;
        }
        .skeleton-header {
            margin-bottom: 0.7rem;
        }
        .skeleton-description {
            height: 42px;
            margin-bottom: 1rem;
        }
    }

    @media (max-width: 480px) {
        .skeleton-card {
            margin: 0 0 0.5rem 0;
            border-radius: 6px;
            corner-shape: squircle;
        }
        .skeleton-image {
            border-radius: 6px 6px 0 0;
            corner-shape: squircle;
        }
        .skeleton-content {
            padding: 0.7rem 0.7rem 0.5rem;
        }
        .skeleton-description {
            height: 36px;
            margin-bottom: 0.8rem;
        }
        .skeleton-actions {
            gap: 0.2rem;
        }
        .skeleton-button {
            height: 44px;
        }
    }

    @media (max-width: 320px) {
        .skeleton-card {
            margin: 0 0 0.3rem 0;
            border-radius: 8px;
            corner-shape: squircle;
            min-width: unset;
            max-width: 100%;
        }
        .skeleton-image {
            border-radius: 8px 8px 0 0;
            corner-shape: squircle;
        }
        .skeleton-content {
            padding: 0.5rem 0.5rem 0.3rem;
        }
        .skeleton-description {
            height: 32px;
        }
    }
</style>
