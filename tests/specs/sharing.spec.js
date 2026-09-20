import { test, expect } from "@playwright/test";
import { gotoApp, resetMockData } from "../support/test-helpers.js";

// The downloaded PNG and failure screenshots cover the visual output.
test.use({ video: "off" });

test.beforeEach(async ({ request }) => resetMockData(request));

async function mockShare(page, result = "success") {
  await page.addInitScript((result) => {
    window.sharedCards = [];
    Object.defineProperty(navigator, "share", { configurable: true, value: async (data) => {
      window.sharedCards.push(data);
      if (result !== "success") throw new DOMException("Share rejected", result);
    } });
  }, result);
}

test("previews the card but shares only its text and link", async ({ page }) => {
  await mockShare(page);
  await gotoApp(page);
  const card = page.locator(".post").first();
  const description = await card.locator(".description-text").innerText();
  await card.getByRole("button", { name: "Share", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Share incident" });
  await expect(dialog.getByRole("img", { name: /^Incident card at / })).toBeVisible();
  await expect(dialog.getByRole("link", { name: "Download image" })).toBeVisible();
  await dialog.getByRole("button", { name: "Share", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  const [shared] = await page.evaluate(() => window.sharedCards);
  expect(shared.text).toContain(description);
  expect(shared.url).toBe(new URL(page.url()).origin);
  expect(shared.title).toBe("San Diego Traffic Watch");
  expect(shared).not.toHaveProperty("files");
  await expect(card.getByRole("button", { name: "Share", exact: true })).toBeFocused();
});

test("downloads the preview image separately from sharing", async ({ page }, testInfo) => {
  await gotoApp(page);
  const card = page.locator(".post").first();
  await expect(card.locator(".mini-map.ready")).toBeVisible({ timeout: 15000 });
  await card.getByRole("button", { name: "Share", exact: true }).click();
  const dialog = page.getByRole("dialog");
  const downloadLink = dialog.getByRole("link", { name: "Download image" });
  await expect(downloadLink).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Share", exact: true })).toBeEnabled();
  const image = await dialog.getByRole("img", { name: /^Incident card at / }).evaluate(async (image) => {
    const blob = await (await fetch(image.src)).blob();
    return { type: blob.type, signature: Array.from(new Uint8Array(await blob.slice(0, 8).arrayBuffer())) };
  });
  expect(image.type).toBe("image/png");
  expect(image.signature).toEqual([137, 80, 78, 71, 13, 10, 26, 10]);
  const downloading = page.waitForEvent("download");
  await downloadLink.click();
  const download = await downloading;
  expect(download.suggestedFilename()).toMatch(/^san-diego-watch-.*\.png$/);
  await download.saveAs(testInfo.outputPath("shared-card.png"));
  await testInfo.attach("shared-card", { path: testInfo.outputPath("shared-card.png"), contentType: "image/png" });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});

for (const result of ["AbortError", "NotAllowedError"]) {
  test(`handles native share ${result} without an unhandled rejection`, async ({ page }) => {
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await mockShare(page, result);
    await gotoApp(page);
    await page.locator(".post").first().getByRole("button", { name: "Share", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Share", exact: true }).click();
    await expect.poll(() => page.evaluate(() => window.sharedCards.length)).toBe(1);
    await expect(dialog.getByRole("button", { name: "Share", exact: true })).toBeEnabled();
    if (result === "AbortError") await expect(dialog.getByRole("alert")).toHaveCount(0);
    else await expect(dialog.getByRole("alert")).toContainText("Could not share");
    expect(errors).toEqual([]);
  });
}

test("shares an expanded table incident with its row header and details", async ({ page }) => {
  await mockShare(page);
  await gotoApp(page);
  await page.getByRole("button", { name: "Condense to table view" }).click();
  await page.locator(".table-row .type-cell").first().click();
  await page.locator(".expanded-details").getByRole("button", { name: "Share", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("img", { name: /^Incident card at / })).toBeVisible();
  await dialog.getByRole("button", { name: "Share", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  const [shared] = await page.evaluate(() => window.sharedCards);
  expect(shared.text).toContain("SIG Alert blocking two lanes near I-5 downtown.");
  expect(shared).not.toHaveProperty("files");
});

test("opens the original text-and-link tweet composer without native sharing", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "share", { configurable: true, value: undefined });
    window.open = (...args) => { window.shareWindowArgs = args; return null; };
  });
  await gotoApp(page);
  const card = page.locator(".post").first();
  const description = await card.locator(".description-text").innerText();
  await card.getByRole("button", { name: "Share", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Share", exact: true }).click();
  const [target, name, features] = await page.evaluate(() => window.shareWindowArgs);
  const composer = new URL(target);
  expect(composer.origin + composer.pathname).toBe("https://twitter.com/intent/tweet");
  expect(composer.searchParams.get("text")).toContain(description);
  expect(composer.searchParams.get("url")).toBe(new URL(page.url()).origin);
  expect([...composer.searchParams.keys()].sort()).toEqual(["text", "url"]);
  expect(name).toBe("_blank");
  expect(features).toBe("noopener,noreferrer");
});
