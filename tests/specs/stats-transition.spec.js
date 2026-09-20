import { test, expect } from "@playwright/test";
import { gotoApp, resetMockData } from "../support/test-helpers.js";

test.beforeEach(async ({ request }) => resetMockData(request));

async function sampleToggle(page) {
  return page.evaluate(async () => {
    const panel = document.querySelector("#incident-stats");
    const button = document.querySelector('[aria-controls="incident-stats"]');
    const content = panel.firstElementChild;
    const samples = [];
    const opening = button.getAttribute("aria-expanded") !== "true";
    button.click();
    const start = performance.now();
    let settledAt = null;
    while (performance.now() - start < 8000) {
      await new Promise(requestAnimationFrame);
      const height = panel.getBoundingClientRect().height;
      const target = opening ? content.getBoundingClientRect().height : 0;
      const header = document.querySelector("header").getBoundingClientRect();
      samples.push({ height, opacity: getComputedStyle(panel).opacity,
        gap: panel.getBoundingClientRect().top - header.bottom });
      if ((!opening || target > 0) && Math.abs(height - target) < 1) {
        settledAt ??= performance.now();
        if (performance.now() - settledAt > 100) break;
      } else settledAt = null;
    }
    return samples;
  });
}

for (const width of [1280, 390]) {
  test(`stats slide on first load and close without fading at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await gotoApp(page);
    const opening = await sampleToggle(page);
    const fullHeight = opening.at(-1).height;
    expect(fullHeight).toBeGreaterThan(100);
    expect(opening.some(frame => frame.height > 1 && frame.height < fullHeight - 1)).toBe(true);
    expect(opening.every(frame => frame.opacity === "1" && Math.abs(frame.gap) < 1)).toBe(true);

    const closing = await sampleToggle(page);
    expect(closing.some(frame => frame.height > 1 && frame.height < fullHeight - 1)).toBe(true);
    expect(closing.at(-1).height).toBe(0);
    expect(closing.every(frame => frame.opacity === "1")).toBe(true);
    await expect(page.locator(".event-counters")).toBeHidden();
    await expect(page.locator(".event-counters")).toHaveCount(1);
  });
}

test("rapid toggles reverse smoothly and resizing preserves the full panel", async ({ page }) => {
  await gotoApp(page);
  await sampleToggle(page);
  const results = await page.evaluate(async () => {
    const panel = document.querySelector("#incident-stats");
    const button = document.querySelector('[aria-controls="incident-stats"]');
    const fullHeight = panel.getBoundingClientRect().height;
    button.click();
    while (panel.getBoundingClientRect().height >= fullHeight - 1) {
      await new Promise(requestAnimationFrame);
    }
    const before = panel.getBoundingClientRect().height;
    button.click();
    const after = panel.getBoundingClientRect().height;
    return { before, after };
  });
  expect(Math.abs(results.before - results.after)).toBeLessThan(2);
  await page.setViewportSize({ width: 390, height: 900 });
  await expect.poll(() => page.locator("#incident-stats").evaluate(panel =>
    Math.abs(panel.getBoundingClientRect().height - panel.firstElementChild.getBoundingClientRect().height),
  )).toBeLessThan(1);
  await expect(page.getByRole("button", { name: "Stats", exact: true })).toHaveAttribute("aria-expanded", "true");
});

test("reduced motion opens and closes without a long transition", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await gotoApp(page);
  await sampleToggle(page);
  const panel = page.locator("#incident-stats");
  expect(await panel.evaluate(node => parseFloat(getComputedStyle(node).transitionDuration))).toBeLessThan(0.01);
  await sampleToggle(page);
  await expect(page.locator(".event-counters")).toBeHidden();
});
