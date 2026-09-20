// Animate a real height so lazy-loaded content and later data/layout changes
// expand from the current position instead of jumping to an intrinsic size.
export function expandPanel(node, expanded) {
  const content = node.firstElementChild;
  const resize = () => {
    node.style.height = expanded ? `${content.getBoundingClientRect().height}px` : "0px";
  };

  node.style.height = "0px";
  const observer = new ResizeObserver(resize);
  observer.observe(content);

  return {
    update(value) {
      expanded = value;
      resize();
    },
    destroy() {
      observer.disconnect();
    },
  };
}
