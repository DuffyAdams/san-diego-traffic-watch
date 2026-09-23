import { cubicOut } from "svelte/easing";
import { fade as svelteFade, slide as svelteSlide } from "svelte/transition";

export function motionDuration(duration) {
  if (typeof window === "undefined") return 0;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
    document.body.classList.contains("accessibility-mode") ? 0 : duration;
}

// Svelte transitions use Web Animations, which CSS duration overrides cannot stop.
function respectMotion(transition) {
  return (node, options = {}, context) => transition(node, {
    easing: cubicOut,
    ...options,
    duration: motionDuration(options.duration ?? 250),
    delay: motionDuration(options.delay ?? 0),
  }, context);
}

export const fade = respectMotion(svelteFade);
export const slide = respectMotion(svelteSlide);

// Reveal from the bottom edge; closing retraces the same path downward.
// Clipping preserves the overlay's layout and scroll area throughout motion.
export const revealUp = respectMotion((node, options) => ({
  ...options,
  css: (t) => `clip-path: inset(${(1 - t) * 100}% 0 0 0)`,
}));
