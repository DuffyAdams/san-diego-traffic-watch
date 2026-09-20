import { readable } from "svelte/store";

// One listener shared by the feed, map and clock; removed with the last subscriber.
export const pageVisible = readable(true, (set) => {
  if (typeof document === "undefined") return;
  const update = () => set(!document.hidden);
  update();
  document.addEventListener("visibilitychange", update);
  return () => document.removeEventListener("visibilitychange", update);
});

// Relative timestamps retain second precision without a timer per incident.
export const liveClock = readable(Date.now(), (set) => {
  let timer;
  const unsubscribe = pageVisible.subscribe((visible) => {
    clearInterval(timer);
    if (visible) {
      set(Date.now());
      timer = setInterval(() => set(Date.now()), 1000);
    }
  });
  return () => {
    clearInterval(timer);
    unsubscribe();
  };
});
