import { test, expect } from '@playwright/test';
import { gotoApp, resetMockData } from '../support/test-helpers.js';

test.beforeEach(async ({ request }) => resetMockData(request));

async function openComparison(page, previousWeekHourlyData) {
  await page.route('**/api/incident_stats?**', async route => {
    const response = await route.fetch();
    const data = await response.json();
    const day = new URL(route.request().url()).searchParams.get('date_filter') === 'day';
    await route.fulfill({ json: {
      ...data,
      ...(day ? { hourlyData: Array(24).fill(4) } : {}),
      previousPeriodData: day ? previousWeekHourlyData : data.previousPeriodData,
      previousWeekHourlyData: day ? previousWeekHourlyData : null,
    } });
  });
  await gotoApp(page);
  await page.getByRole('button', { name: 'Stats', exact: true }).click();
}

for (const width of [320, 390, 1280]) {
  test(`last week sits behind current activity on a shared scale at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await openComparison(page, Array(24).fill(20));
    await expect(page.locator('.comparison-bar')).toHaveCount(24);
    await expect(page.locator('.chart-legend')).toHaveText('Current Last week');
    const bucket = page.locator('.bar-wrapper').nth(12);
    await expect(bucket).toHaveAttribute('aria-label', /Current: 4 incidents.*Last week: 20 incidents/);
    await expect.poll(async () => bucket.evaluate(el => {
      const current = el.querySelector('.bar').getBoundingClientRect();
      const previous = el.querySelector('.comparison-bar').getBoundingClientRect();
      return Math.abs(current.height / previous.height - 0.2);
    })).toBeLessThan(0.01);
    const bars = await bucket.evaluate(el => {
      const current = el.querySelector('.bar').getBoundingClientRect();
      const previous = el.querySelector('.comparison-bar').getBoundingClientRect();
      return { currentWidth: current.width, previousWidth: previous.width, bottomDelta: current.bottom - previous.bottom };
    });
    expect(bars.currentWidth).toBeCloseTo(bars.previousWidth, 1);
    expect(Math.abs(bars.bottomDelta)).toBeLessThan(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
    if (width < 768) expect(await page.locator('.event-counters').evaluate(el => el.offsetHeight)).toBeLessThan(620);
    await bucket.hover();
    await expect(page.locator('.chart-tooltip')).toContainText('Last week: 20');
    for (const [period, length, label] of [['Week', 7, 'Previous'], ['Month', 30, 'Previous'], ['Year', 12, 'Previous']]) {
      await page.getByRole('button', { name: period, exact: true }).click();
      await expect(page.locator('.comparison-bar')).toHaveCount(length);
      await expect(page.locator('.chart-legend')).toContainText(label);
      await expect(page.locator('.activity-chart-section .status-indicator')).toHaveCount(0);
      await expect(page.locator('.x-label').first()).not.toBeEmpty();
    }
    // Returning to the cached day response must restore the comparison too.
    await page.getByRole('button', { name: '1 day', exact: true }).click();
    await expect(page.locator('.comparison-bar')).toHaveCount(24);
  });
}

for (const [name, history] of [['missing', null], ['incomplete', [4, 5]], ['zero', Array(24).fill(0)]]) {
  test(`${name} history is distinguished from recorded activity`, async ({ page }) => {
    await openComparison(page, history);
    if (name === 'zero') {
      await expect(page.locator('.comparison-bar.empty')).toHaveCount(24);
      await expect(page.locator('.chart-legend')).toContainText('Last week');
    } else {
      await expect(page.locator('.comparison-bar')).toHaveCount(0);
      await expect(page.locator('.chart-legend')).toContainText('Last week unavailable');
    }
  });
}

for (const width of [320, 390, 1280]) {
  test(`seeded history provides all comparisons and source filtering at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await gotoApp(page);
    await page.getByRole('button', { name: 'Stats', exact: true }).click();
    for (const [period, length, label] of [['1 day', 24, 'Last week'], ['Week', 7, 'Previous'], ['Month', 30, 'Previous'], ['Year', 12, 'Previous']]) {
      await page.getByRole('button', { name: period, exact: true }).click();
      await expect(page.locator('.comparison-bar')).toHaveCount(length);
      await expect(page.locator('.chart-legend')).toContainText(label);
      expect(await page.locator('.comparison-bar:not(.empty)').count()).toBeGreaterThan(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
      const labels = await page.locator('.x-label-container:not(.mobile-hide-label) .x-label').allTextContents();
      expect(labels.every(label => label.trim().length > 0)).toBe(true);
    }
    const response = page.waitForResponse(response => response.url().includes('/api/incident_stats?') && response.url().includes('source=SDPD'));
    await page.getByRole('button', { name: 'SDPD', exact: true }).click();
    const data = await (await response).json();
    expect(data.previousPeriodData.some(count => count > 0)).toBe(true);
    await expect(page.locator('.comparison-bar')).toHaveCount(data.previousPeriodData.length);
  });
}

for (const period of ['week', 'month', 'year']) {
  test(`${period} with no history stays explicit and keeps current data visible`, async ({ page }) => {
    await page.route('**/api/incident_stats?**', async route => {
      const response = await route.fetch();
      await route.fulfill({ json: { ...await response.json(), previousPeriodData: null, previousWeekHourlyData: null } });
    });
    await gotoApp(page);
    await page.getByRole('button', { name: 'Stats', exact: true }).click();
    await page.getByRole('button', { name: period[0].toUpperCase() + period.slice(1), exact: true }).click();
    await expect(page.locator('.chart-legend')).toContainText('Previous period unavailable');
    await expect(page.locator('.comparison-bar')).toHaveCount(0);
    expect(await page.locator('.bar').count()).toBeGreaterThan(0);
  });
}
