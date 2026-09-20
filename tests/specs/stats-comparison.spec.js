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
    await expect(page.locator('.chart-legend')).toHaveText('Last 24 hours Same hours last week');
    const bucket = page.locator('.bar-wrapper').nth(12);
    await expect(bucket).toHaveAttribute('aria-label', /4 incidents.*20 in the same hour last week/);
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
    expect(bars.currentWidth).toBeLessThan(bars.previousWidth);
    expect(Math.abs(bars.bottomDelta)).toBeLessThan(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
    if (width < 768) expect(await page.locator('.event-counters').evaluate(el => el.offsetHeight)).toBeLessThan(620);
    await bucket.hover();
    await expect(page.locator('.chart-tooltip')).toContainText('Same hours last week: 20 incidents');
    for (const period of ['Week', 'Month', 'Year']) {
      await page.getByRole('button', { name: period, exact: true }).click();
      await expect(page.locator('.comparison-bar')).toHaveCount(0);
      await expect(page.locator('.chart-legend')).toHaveCount(0);
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
      await expect(page.locator('.chart-legend')).toContainText('Same hours last week');
    } else {
      await expect(page.locator('.comparison-bar')).toHaveCount(0);
      await expect(page.locator('.chart-legend')).toContainText('Last week unavailable');
    }
  });
}
