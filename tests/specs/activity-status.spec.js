import { test, expect } from "@playwright/test";
import { gotoApp, resetMockData } from "../support/test-helpers.js";

test.beforeEach(async ({ request }) => resetMockData(request));

async function openStats(page, overrides) {
  await page.route("**/api/incident_stats?**", async (route) => {
    const response = await route.fetch();
    await route.fulfill({ json: { ...await response.json(), ...overrides } });
  });
  await gotoApp(page);
  await page.getByRole("button", { name: /^stats$/i }).click();
}

test("uses last-hour volume with a compact status; historical views have no hourly alert", async ({ page }) => {
  await openStats(page, {
    eventsLastHour: 10, historicalCurrentHourAverage: 10, historicalHourSampleCount: 6,
    hourlyData: Array(24).fill(100),
  });
  await expect(page.locator(".activity-chart-section .status-indicator")).toHaveText("Typical activity");
  await expect(page.locator(".activity-context")).toHaveCount(0);
  for (const name of ["Week", "Month", "Year"]) {
    await page.getByRole("button", { name, exact: true }).click();
    await expect(page.locator(".activity-chart-section .status-indicator")).toHaveCount(0);
    await expect(page.locator(".bar.spike")).toHaveCount(0);
  }
  await page.getByRole("button", { name: "1 day", exact: true }).click();
  await expect(page.locator(".activity-chart-section .status-indicator")).toHaveText("Typical activity");
});

test("missing baseline stays neutral even with incidents", async ({ page }) => {
  await openStats(page, {
    eventsLastHour: 20, historicalCurrentHourAverage: 0, historicalHourSampleCount: 0,
  });
  await expect(page.locator(".activity-chart-section .status-indicator")).toHaveText("Building baseline");
  await expect(page.locator(".activity-context")).toHaveCount(0);
});

test("empty chart data is not presented as typical activity", async ({ page }) => {
  await openStats(page, { hourlyData: [], eventsLastHour: 0 });
  await expect(page.locator(".activity-chart-section .status-indicator")).toHaveText("No data");
});

test("high volume does not claim critical incident severity or require a daily peak", async ({ page }) => {
  await openStats(page, {
    eventsLastHour: 20, historicalCurrentHourAverage: 10, historicalHourSampleCount: 6,
    hourlyData: [...Array(23).fill(40), 20],
  });
  await expect(page.locator(".activity-chart-section .status-indicator")).toHaveText("High activity");
  await expect(page.locator(".bar.spike")).toHaveCount(1);
});
