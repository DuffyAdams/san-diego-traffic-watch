// Read WebGL pixels during a render, before the drawing buffer is cleared.
// This avoids enabling preserveDrawingBuffer on every feed map.
const mapSources = new WeakMap();

export function shareableMap(node, getMap) {
  mapSources.set(node, getMap);
  return { destroy: () => mapSources.delete(node) };
}

function snapshotMap(map) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      map.off("render", capture);
      reject(new Error("Map snapshot timed out"));
    }, 2000);
    function capture() {
      clearTimeout(timeout);
      try {
        resolve({ canvas: map.getCanvas(), url: map.getCanvas().toDataURL() });
      } catch (error) {
        reject(error);
      }
    }
    map.once("render", capture);
    map.triggerRepaint();
  });
}

export async function createShareImage(elements, postId) {
  const { toCanvas } = await import("html-to-image");
  const snapshots = [];
  try {
    for (const element of elements) {
      for (const shell of element.querySelectorAll(".mini-map-shell")) {
        const map = mapSources.get(shell)?.();
        if (!map) continue;
        const { canvas, url } = await snapshotMap(map);
        const image = new Image();
        image.src = url;
        image.style.cssText = canvas.style.cssText;
        image.style.position = "absolute";
        image.style.left = "0";
        image.style.top = "0";
        image.alt = "";
        canvas.after(image);
        snapshots.push(image);
      }
    }

    const backgroundColor = getComputedStyle(elements[0])
      .getPropertyValue("--bg-surface").trim() || "#1a1d25";
    const captures = [];
    for (const element of elements) {
      captures.push(await toCanvas(element, {
        pixelRatio: 2,
        backgroundColor,
        // The app uses system fonts; avoid fetching unrelated web stylesheets.
        skipFonts: true,
        style: { transform: "none", animation: "none", opacity: "1" },
        filter: (node) => !node.matches?.(
          "canvas, .post-actions, .expanded-actions, .comments-overlay, .raw-details-inline-overlay, .raw-details-button, .more-button",
        ),
      }));
    }
    const output = document.createElement("canvas");
    output.width = Math.max(...captures.map((canvas) => canvas.width));
    output.height = captures.reduce((height, canvas) => height + canvas.height, 0);
    const context = output.getContext("2d");
    context.fillStyle = backgroundColor;
    context.fillRect(0, 0, output.width, output.height);
    let top = 0;
    for (const canvas of captures) {
      context.drawImage(canvas, 0, top);
      top += canvas.height;
    }
    const blob = await new Promise((resolve) => output.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("Could not create card image");
    const safeId = String(postId).replace(/[^a-z0-9_-]/gi, "-").slice(0, 80);
    return new File([blob], `san-diego-watch-${safeId}.png`, { type: "image/png" });
  } finally {
    snapshots.forEach((image) => image.remove());
  }
}
