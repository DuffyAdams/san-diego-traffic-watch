import { test, expect } from '@playwright/test';

const labels = ['Traffic', 'SDPD', 'Sheriff', 'Fire', 'Map'];

async function checkTabs(page, width, stacked = true, checkPage = true) {
  const nav = page.getByRole('navigation', { name: 'Incident sources' });
  await expect(nav.getByRole('button')).toHaveText(labels);
  const geometry = await nav.evaluate(el => ({
    scroll: el.scrollWidth, client: el.clientWidth,
    pageScroll: document.documentElement.scrollWidth,
    buttons: [...el.querySelectorAll('button')].map(button => {
      const b = button.getBoundingClientRect();
      const label = button.querySelector('span');
      const l = label.getBoundingClientRect();
      const icon = button.querySelector('svg').getBoundingClientRect();
      return { x: b.x, right: b.right, width: b.width, height: b.height,
        labelScroll: label.scrollWidth, labelClient: label.clientWidth,
        labelRight: l.right, labelBottom: l.bottom, bottom: b.bottom,
        labelTop: l.top, iconBottom: icon.bottom };
    }),
  }));
  expect(geometry.scroll).toBeLessThanOrEqual(geometry.client + 1);
  if (checkPage) expect(geometry.pageScroll).toBeLessThanOrEqual(width);
  for (const b of geometry.buttons) {
    expect(b.x).toBeGreaterThanOrEqual(0);
    expect(b.right).toBeLessThanOrEqual(width);
    expect(b.width).toBeGreaterThanOrEqual(44);
    expect(b.height).toBeGreaterThanOrEqual(stacked ? 44 : 40);
    expect(b.labelScroll).toBeLessThanOrEqual(b.labelClient + 1);
    expect(b.labelRight).toBeLessThanOrEqual(b.right);
    expect(b.labelBottom).toBeLessThanOrEqual(b.bottom);
    if (stacked) expect(b.labelTop).toBeGreaterThanOrEqual(b.iconBottom);
  }
  if (stacked) expect(Math.max(...geometry.buttons.map(b => b.width)) - Math.min(...geometry.buttons.map(b => b.width))).toBeLessThan(1);
  return geometry;
}

for (const width of [320, 375, 390, 430, 1280]) {
  test(`single-row search takeover at ${width}px`, async ({ browser }, testInfo) => {
    const context = await browser.newContext({ viewport: { width, height: 900 }, isMobile: width <= 650, hasTouch: true, baseURL: testInfo.project.use.baseURL });
    const page = await context.newPage();
    await page.goto('/');
    const nav = page.getByRole('navigation', { name: 'Incident sources' });
    await expect(nav.getByRole('button', { name: 'Traffic', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await checkTabs(page, width, width <= 650);
    const before = await page.locator('.toolbar').boundingBox();
    const icon = await page.locator('.search-toggle').boundingBox();
    const tabs = await nav.boundingBox();
    expect(Math.abs(icon.y + icon.height / 2 - tabs.y - tabs.height / 2)).toBeLessThan(1);
    expect(icon.width).toBeGreaterThanOrEqual(44);
    expect(icon.height).toBeGreaterThanOrEqual(44);
    await page.locator('.search-toggle').tap();
    await expect(page.getByRole('searchbox')).toBeFocused();
    if (width <= 650) await expect(nav).toBeHidden();
    await page.getByRole('searchbox').pressSequentially('Main');
    await page.waitForTimeout(350);
    const after = await page.locator('.toolbar').boundingBox();
    expect(after.height).toBeCloseTo(before.height, 1);
    if (width <= 650) {
      const search = await page.locator('.search-container').boundingBox();
      expect(search.width).toBeGreaterThan(before.width - 18);
      await expect(page.getByRole('button', { name: 'Traffic', exact: true })).toHaveCount(0);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await page.screenshot({ path: testInfo.outputPath(`search-${width}-expanded.png`), fullPage: true });
    await page.getByRole('button', { name: 'Close search', exact: true }).click();
    await expect(page.locator('.search-toggle')).toBeFocused();
    await checkTabs(page, width, width <= 650);
    await page.locator('.search-toggle').tap();
    await expect(page.getByRole('searchbox')).toHaveValue('Main');
    await page.getByRole('button', { name: 'Clear search', exact: true }).click();
    await expect(page.getByRole('searchbox')).toHaveValue('');
    await expect(page.getByRole('searchbox')).toBeFocused();
    await page.getByRole('searchbox').press('Escape');
    await expect(page.locator('.search-toggle')).toHaveAttribute('aria-expanded', 'false');
    const geometry = await checkTabs(page, width, width <= 650);
    if (width === 390) {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.locator('.search-toggle').tap();
      for (const selector of ['.search-wrapper', '.search-container', '.search-field']) {
        expect(await page.locator(selector).evaluate(el => parseFloat(getComputedStyle(el).transitionDuration))).toBeLessThan(0.001);
      }
      await page.getByRole('searchbox').press('Escape');
      await expect(nav).toBeVisible();
    }
    await testInfo.attach('tab-geometry', { body: JSON.stringify(geometry, null, 2), contentType: 'application/json' });
    await page.screenshot({ path: testInfo.outputPath(`tabs-${width}-normal.png`), fullPage: true });
    if (width <= 650) {
      await page.evaluate(() => { document.documentElement.style.fontSize = '32px'; });
      // Existing feed/header text-zoom overflow is outside this navigation fix.
      await checkTabs(page, width, true, false);
    }
    await page.screenshot({ path: testInfo.outputPath(`tabs-${width}.png`), fullPage: true });
    await context.close();
  });
}

test('map search returns to CHP, never a hidden All source', async ({ page }) => {
  const initialRequest = page.waitForRequest(req => req.url().includes('/api/incidents') && new URL(req.url()).searchParams.get('source') === 'CHP');
  await page.goto('/');
  await initialRequest;
  const nav = page.getByRole('navigation', { name: 'Incident sources' });
  await nav.getByRole('button', { name: 'Map', exact: true }).click();
  await expect(nav.getByRole('button', { name: 'Map', exact: true })).toHaveAttribute('aria-pressed', 'true');

  await page.locator('.search-toggle').click();
  await expect(nav.getByRole('button', { name: 'Traffic', exact: true })).toHaveAttribute('aria-pressed', 'true');
  // Returning to CHP may reuse the initial cached response.
  await expect(nav.getByRole('button', { pressed: true })).toHaveCount(1);
});

test('isolated SourceTabs defaults to Traffic and dispatches all five source values', async ({ page }) => {
  // Same real-component Vite harness used by ticker-controls.spec.js.
  await page.route('**/ui-regression-harness', route => route.fulfill({ contentType: 'text/html', body: '<html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body style="margin:0"><div id="fixture"></div></body></html>' }));
  await page.goto('/ui-regression-harness');
  await page.evaluate(async () => {
    const { createClassComponent } = await import('/node_modules/.vite/deps/svelte_legacy.js');
    await import('/src/app.css');
    const { default: Component } = await import('/src/components/ui/SourceTabs.svelte');
    window.sources = [];
    window.fixture = createClassComponent({ component: Component, target: document.querySelector('#fixture'), props: {} });
    window.fixture.$on('changeSource', event => { window.sources.push(event.detail); window.fixture.$set({ activeSource: event.detail }); });
  });
  const nav = page.getByRole('navigation', { name: 'Incident sources' });
  await expect(nav.getByRole('button')).toHaveText(labels);
  await expect(nav.getByRole('button', { name: 'Traffic', exact: true })).toHaveAttribute('aria-pressed', 'true');
  for (const label of labels) {
    const button = nav.getByRole('button', { name: label, exact: true });
    await button.focus();
    await button.press('Enter');
    await expect(button).toHaveAttribute('aria-pressed', 'true');
  }
  expect(await page.evaluate(() => window.sources)).toEqual(['CHP', 'SDPD', 'SDSO', 'SDFD', 'map']);
});
