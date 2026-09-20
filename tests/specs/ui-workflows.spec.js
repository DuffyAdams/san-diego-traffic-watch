import { test, expect } from "@playwright/test";
import { gotoApp, resetMockData } from "../support/test-helpers.js";

test.beforeEach(async ({ request }) => {
  await resetMockData(request);
});

test("loads the incident feed and supports source filtering", async ({ page }) => {
  await gotoApp(page);

  await expect(page.getByText("SIG Alert blocking two lanes near I-5 downtown.")).toBeVisible();
  await expect(
    page.getByText(
      "Police activity has closed Harbor Drive near the Convention Center.",
    ),
  ).toBeVisible();

  const sourceResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/incidents") &&
      response.url().includes("source=SDPD") &&
      response.status() === 200,
  );

  await page.getByRole("button", { name: "SDPD" }).click();
  await sourceResponse;

  await expect(
    page.getByText(
      "Police activity has closed Harbor Drive near the Convention Center.",
    ),
  ).toBeVisible();
  await expect(page.getByText("SIG Alert blocking two lanes near I-5 downtown.")).not.toBeVisible();
});

test("supports diagnostics, search, and comment submission", async ({ page }) => {
  await gotoApp(page);

  await page.getByRole("button", { name: /^stats$/i }).click();
  await expect(page.getByText("24-Hour Activity")).toBeVisible();
  await expect(page.getByText("Today")).toBeVisible();
  await expect(page.getByRole("button", { name: "Week" })).toBeVisible();

  const latestActivityBar = page.locator(".bar-wrapper").last();
  await latestActivityBar.hover();
  const activityTooltip = page.locator(".chart-tooltip");
  await expect(activityTooltip.locator(".tooltip-value").first()).toContainText(/\d/);
  await latestActivityBar.hover({ force: true });
  await expect(activityTooltip).toBeVisible();
  const tooltipContrast = await activityTooltip.evaluate((tooltip) => {
    const channels = (color) => color.match(/[\d.]+/g).slice(0, 3).map(Number);
    const luminance = (color) => {
      const [red, green, blue] = channels(color).map((channel) => {
        const value = channel / 255;
        return value <= 0.04045
          ? value / 12.92
          : ((value + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
    };
    const foreground = luminance(
      getComputedStyle(tooltip.querySelector(".tooltip-value")).color,
    );
    const background = luminance(getComputedStyle(tooltip).backgroundColor);
    return (Math.max(foreground, background) + 0.05) /
      (Math.min(foreground, background) + 0.05);
  });
  expect(tooltipContrast).toBeGreaterThanOrEqual(4.5);

  const statsButton = page.getByRole("button", { name: /^stats$/i });
  const statsShell = page.locator(".stats-panel-shell");
  await statsButton.click();
  await expect(statsShell).toHaveAttribute("aria-hidden", "true");
  await expect(statsShell.locator(".event-counters")).toHaveCount(1);
  await statsButton.click();
  await expect(statsShell).toHaveAttribute("aria-hidden", "false");
  await expect(statsShell.locator(".event-counters")).toBeVisible();

  await page.getByPlaceholder("Search incidents...").fill("North Park");
  await expect(page.getByText("Traffic accident with injuries near North Park.")).toBeVisible();
  await expect(
    page.getByText(
      "Police activity has closed Harbor Drive near the Convention Center.",
    ),
  ).not.toBeVisible();

  const northParkCard = page.locator(".post").filter({
    hasText: "Traffic accident with injuries near North Park.",
  });
  await northParkCard.getByRole("button", { name: /^Comment/i }).click();
  await page.getByPlaceholder("Write a comment...").fill("Detour confirmed.");
  await page.getByRole("button", { name: /send/i }).click();

  await expect(page.getByText("Comment added successfully!")).toBeVisible();
  await expect(page.getByText("Detour confirmed.")).toBeVisible();
});
