<script>
    // Defer image loading until the element approaches the viewport.
    import { onMount } from "svelte";

    export let src;
    export let alt = "";
    export let className = "";
    export let priority = false;

    let img;
    let isLoaded = false;
    let isInView = false;
    let hasError = false;

    // Create intersection observer for lazy loading
    let observer;

    onMount(() => {
        if (priority) {
            // Priority images load immediately
            isInView = true;
        } else {
            // Non-priority images use intersection observer
            observer = new IntersectionObserver(
                (entries) => {
                    entries.forEach((entry) => {
                        if (entry.isIntersecting) {
                            isInView = true;
                            observer.unobserve(entry.target);
                        }
                    });
                },
                {
                    rootMargin: "50px", // Start loading 50px before element enters viewport
                    threshold: 0.1,
                }
            );

            if (img) {
                observer.observe(img);
            }
        }

        return () => {
            if (observer && img) {
                observer.unobserve(img);
            }
        };
    });

    function handleLoad() {
        isLoaded = true;
    }

    function handleError() {
        hasError = true;
    }
</script>

{#if isInView}
    <div class="image-shell {className}" class:loaded={isLoaded}>
        <img
            bind:this={img}
            {src}
            {alt}
            class="lazy-image"
            class:loaded={isLoaded}
            on:load={handleLoad}
            on:error={handleError}
        />
        {#if !isLoaded && !hasError}
            <div class="image-loading-overlay"></div>
        {/if}
    </div>
{:else}
    <!-- Placeholder while not in view -->
    <div
        bind:this={img}
        class="image-placeholder {className}"
    ></div>
{/if}

<style>
    .image-shell {
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
        border-radius: inherit;
        background: #0f172a;
    }

    .lazy-image {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
        filter: blur(18px);
        transform: scale(1.04);
        opacity: 0.72;
        transition:
            filter 280ms ease,
            opacity 280ms ease,
            transform 280ms ease;
    }

    .lazy-image.loaded {
        filter: blur(0);
        transform: scale(1);
        opacity: 1;
    }

    .image-loading-overlay {
        position: absolute;
        inset: 0;
        background: linear-gradient(
            90deg,
            rgba(255, 255, 255, 0.04) 0%,
            rgba(255, 255, 255, 0.12) 50%,
            rgba(255, 255, 255, 0.04) 100%
        );
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        pointer-events: none;
    }

    .image-placeholder {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 8px;
        corner-shape: squircle;
    }

    @keyframes shimmer {
        0% {
            background-position: -200% 0;
        }
        100% {
            background-position: 200% 0;
        }
    }
</style>
