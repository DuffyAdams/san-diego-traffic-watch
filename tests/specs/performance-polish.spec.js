import { test, expect } from "@playwright/test";
import { gotoApp, resetMockData } from "../support/test-helpers.js";

test.beforeEach(async ({ request }) => resetMockData(request));

async function setPageHidden(page, hidden) {
  await page.evaluate((value) => {
    Object.defineProperty(document, "hidden", { configurable: true, value });
    document.dispatchEvent(new Event("visibilitychange"));
  }, hidden);
}

test("many incident timestamps share one timer and stop while hidden", async ({ page }) => {
  await page.addInitScript(() => {
    const nativeSet = window.setInterval;
    const nativeClear = window.clearInterval;
    window.secondTimers = new Set();
    window.setInterval = (callback, delay, ...args) => {
      const id = nativeSet(callback, delay, ...args);
      if (delay === 1000) window.secondTimers.add(id);
      return id;
    };
    window.clearInterval = (id) => {
      window.secondTimers.delete(id);
      nativeClear(id);
    };
  });
  await gotoApp(page);
  expect(await page.locator(".timestamp-container").count()).toBeGreaterThan(1);
  expect(await page.evaluate(() => window.secondTimers.size)).toBe(1);
  await setPageHidden(page, true);
  expect(await page.evaluate(() => window.secondTimers.size)).toBe(0);
  await setPageHidden(page, false);
  expect(await page.evaluate(() => window.secondTimers.size)).toBe(1);
});

test("feed polling pauses in hidden tabs and resumes immediately", async ({ page }) => {
  await page.clock.install();
  let requests = 0;
  page.on("request", request => {
    if (request.url().includes("/api/incidents?")) requests++;
  });
  await gotoApp(page);
  await setPageHidden(page, true);
  const before = requests;
  await page.clock.fastForward(65000);
  expect(requests).toBe(before);
  const resumed = page.waitForResponse(response => response.url().includes("/api/incidents?"));
  await setPageHidden(page, false);
  await resumed;
  expect(requests).toBe(before + 1);
});

test("a slow refresh is cancelled when the source filter changes", async ({ page }) => {
  await page.clock.install();
  await gotoApp(page);
  let release;
  let started;
  const pending = new Promise(resolve => { started = resolve; });
  await page.route("**/api/incidents?*", async route => {
    const url = new URL(route.request().url());
    if (!url.searchParams.has("source")) {
      started();
      await new Promise(resolve => { release = resolve; });
      await route.fulfill({ json: [{ incident_no: "stale", timestamp: new Date().toISOString(),
        description: "Stale traffic response", location: "I-5", active: true }] }).catch(() => {});
    } else await route.continue();
  });
  await page.clock.fastForward(21000);
  await pending;
  await page.getByRole("button", { name: "SDPD", exact: true }).click();
  await expect(page.locator(".post").first()).toContainText("Police activity");
  release();
  await expect(page.getByText("Stale traffic response", { exact: true })).toHaveCount(0);
});

test("reduced motion disables JavaScript entrance animations", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await gotoApp(page);
  await page.locator(".post").first().getByRole("button", { name: /^Comment/ }).click();
  await expect(page.locator(".comments-overlay")).toBeVisible();
  const durations = await page.locator(".comments-overlay").evaluate(node =>
    node.getAnimations().map(animation => animation.effect.getTiming().duration));
  expect(durations.every(duration => Number(duration) <= 1)).toBeTruthy();
  await page.getByRole("button", { name: "Close comments" }).click();
  await expect(page.locator(".comments-overlay")).toHaveCount(0);
});

test("the full map suspends its own polling while the document is hidden", async ({ page }) => {
  await page.clock.install();
  await gotoApp(page);
  const initial = page.waitForResponse(response => response.url().includes("limit=150"));
  await page.getByRole("button", { name: /^map$/i }).click();
  await initial;
  let requests = 0;
  page.on("request", request => {
    if (request.url().includes("/api/incidents?")) requests++;
  });
  await setPageHidden(page, true);
  await page.clock.fastForward(65000);
  expect(requests).toBe(0);
  const resumed = page.waitForResponse(response => response.url().includes("limit=150"));
  await setPageHidden(page, false);
  await resumed;
  expect(requests).toBe(1);
});

test("mini maps survive a brief scroll away, then release offscreen canvases", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  // Isolate the scroll grace period from intentional eviction under GPU pressure.
  await page.route("**/api/incidents?*", async route => {
    const response = await route.fetch();
    const incidents = await response.json();
    await route.fulfill({ response, json: incidents.map((incident, index) =>
      index === 0 ? incident : { ...incident, latitude: null, longitude: null }) });
  });
  await gotoApp(page);
  const firstMap = page.locator(".mini-map-shell").first();
  const canvas = firstMap.locator("canvas");
  await expect(canvas).toBeVisible();
  const original = await canvas.elementHandle();
  await page.evaluate(() => window.scrollTo({ top: 950, behavior: "instant" }));
  // Stay below the 700ms deactivation grace period.
  await page.waitForTimeout(150);
  expect(await original.evaluate(node => node.isConnected)).toBeTruthy();
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await expect(canvas).toBeVisible();
  expect(await original.evaluate(node => node.isConnected)).toBeTruthy();
  await page.evaluate(() => window.scrollTo({ top: 950, behavior: "instant" }));
  await expect(canvas).toHaveCount(0);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await expect(canvas).toBeVisible();
});

for (const view of ["cards", "table"]) {
  test(`source switching keeps the page stable in ${view} view, including slow and empty sources`, async ({ page }) => {
    await gotoApp(page);
    if (view === "table") {
      await page.getByRole("button", { name: "Condense to table view" }).click();
      await expect(page.locator(".incidents-table")).toBeVisible();
    }
    const feedSelector = view === "table" ? ".incidents-table" : ".feed";
    const originalFeed = await page.locator(feedSelector).elementHandle();
    const originalHeader = await page.locator(".header-top").elementHandle();
    const headerTop = await originalHeader.evaluate(node => node.getBoundingClientRect().top);
    let documentRequests = 0;
    page.on("request", request => {
      if (request.resourceType() === "document") documentRequests++;
    });

    let releasePolice;
    let releaseSheriff;
    const policeGate = new Promise(resolve => { releasePolice = resolve; });
    const sheriffGate = new Promise(resolve => { releaseSheriff = resolve; });
    const incident = (id, description) => ({ incident_no: id,
      timestamp: new Date().toISOString(), description, location: description, active: true });
    await page.route("**/api/incidents?*", async route => {
      const source = new URL(route.request().url()).searchParams.get("source");
      if (source === "SDPD") {
        await policeGate;
        await route.fulfill({ json: [incident("police-test", "Updated police incident")] });
      } else if (source === "SDSO") {
        await sheriffGate;
        await route.fulfill({ json: [incident("sheriff-test", "Stale sheriff incident")] }).catch(() => {});
      } else if (source === "SDFD") {
        await route.fulfill({ json: [] });
      } else await route.continue();
    });

    await page.getByRole("button", { name: "SDPD", exact: true }).click();
    await expect(page.locator(".feed-region")).toHaveAttribute("aria-busy", "true");
    await expect(page.locator(".loading-container")).toHaveCount(0);
    expect(await originalFeed.evaluate(node => node.isConnected)).toBe(true);
    await expect(page.locator(feedSelector)).toContainText("Downtown");
    expect(await originalHeader.evaluate(node => node.getBoundingClientRect().top)).toBe(headerTop);

    releasePolice();
    await expect(page.locator(feedSelector)).toContainText("Updated police incident");
    await expect(page.locator(".feed-region")).toHaveAttribute("aria-busy", "false");
    expect(await originalFeed.evaluate(node => node.isConnected)).toBe(true);
    await expect(page.locator(feedSelector)).not.toContainText("Downtown");

    const sheriffRequest = page.waitForRequest(request => request.url().includes("source=SDSO"));
    await page.getByRole("button", { name: "Sheriff", exact: true }).click();
    await sheriffRequest;
    await page.getByRole("button", { name: "Fire", exact: true }).click();
    await expect(page.locator(".empty-state")).toBeVisible();
    releaseSheriff();
    await expect(page.locator(".feed-region")).toHaveAttribute("aria-busy", "false");
    expect(await originalHeader.evaluate(node => node.isConnected)).toBe(true);
    expect(await originalHeader.evaluate(node => node.getBoundingClientRect().top)).toBe(headerTop);
    await expect(page.getByText("Stale sheriff incident", { exact: true })).toHaveCount(0);

    // Both return trips use the existing response cache without wiping the page.
    await page.getByRole("button", { name: "SDPD", exact: true }).click();
    await expect(page.locator(feedSelector)).toContainText("Updated police incident");
    await page.getByRole("button", { name: "All", exact: true }).click();
    await expect(page.locator(feedSelector)).toContainText("Downtown");
    expect(await originalHeader.evaluate(node => node.getBoundingClientRect().top)).toBe(headerTop);
    expect(documentRequests).toBe(0);
  });
}

test("switching sources during pagination resets the cursor and allows loading more", async ({ page }) => {
  const incidents = (prefix, count) => Array.from({ length: count }, (_, i) => ({
    incident_no: `${prefix}-${i}`, timestamp: new Date(Date.now() - i * 60000).toISOString(),
    description: `${prefix} incident ${i}`, location: prefix, active: true,
  }));
  let releaseOldPage;
  const oldPageGate = new Promise(resolve => { releaseOldPage = resolve; });
  let policeCursor;
  await page.route("**/api/incidents?*", async route => {
    const params = new URL(route.request().url()).searchParams;
    if (params.get("source") === "SDPD") {
      if (params.has("cursor")) {
        policeCursor = params.get("cursor");
        await route.fulfill({ json: incidents("police-next", 1) });
      } else await route.fulfill({ json: incidents("police", 15) });
    } else if (params.has("cursor")) {
      await oldPageGate;
      await route.fulfill({ json: incidents("stale-next", 1) }).catch(() => {});
    } else await route.fulfill({ json: incidents("original", 15) });
  });
  await gotoApp(page);
  const oldRequest = page.waitForRequest(request => new URL(request.url()).searchParams.has("cursor"));
  // Trigger without scrolling so automatic near-bottom loading cannot hide the race.
  await page.locator(".scroll-indicator").dispatchEvent("click");
  await oldRequest;
  await page.getByRole("button", { name: "SDPD", exact: true }).click();
  await expect(page.locator(".post").first()).toContainText("police incident");
  await page.locator(".scroll-indicator").dispatchEvent("click");
  await expect(page.locator(".post")).toHaveCount(16);
  expect(policeCursor).toContain("|police-14");
  releaseOldPage();
  await expect(page.locator(".feed")).not.toContainText("stale-next");
  await expect(page.locator(".feed")).not.toContainText("original incident");
});
