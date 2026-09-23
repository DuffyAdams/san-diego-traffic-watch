import { motionDuration } from "./motion.js";

// Measure the inner content independently so either direction can animate,
// including a toggle made while the previous animation is still running.
export function animateHeight(node) {
  const content = node.firstElementChild;
  let height = content.getBoundingClientRect().height;
  let animation;
  node.style.height = `${height}px`;

  const observer = new ResizeObserver(() => {
    const nextHeight = content.getBoundingClientRect().height;
    if (nextHeight === height) return;
    const currentHeight = node.getBoundingClientRect().height;
    animation?.cancel();
    height = nextHeight;
    node.style.height = `${height}px`;
    node.style.overflow = "";
    const duration = motionDuration(280);
    if (duration) {
      node.style.overflow = "hidden";
      animation = node.animate(
        [{ height: `${currentHeight}px` }, { height: `${height}px` }],
        { duration, easing: "cubic-bezier(0.22, 1, 0.36, 1)" },
      );
      animation.onfinish = () => {
        node.style.overflow = "";
      };
    }
  });
  observer.observe(content);

  return {
    destroy() {
      observer.disconnect();
      animation?.cancel();
    },
  };
}
