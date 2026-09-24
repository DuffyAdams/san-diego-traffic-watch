import { test, expect } from '@playwright/test';

// Isolated real components: no map/network timing or unrelated UI workflows.
async function mountComponent(page, name, props) {
  await page.route('**/ui-regression-harness', route => route.fulfill({
    contentType: 'text/html', body: '<html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body style="margin:0"><div id="fixture"></div></body></html>',
  }));
  await page.goto('/ui-regression-harness');
  await page.evaluate(async ({ name, props }) => {
    const { createClassComponent } = await import('/node_modules/.vite/deps/svelte_legacy.js');
    await import('/src/app.css');
    const { default: Component } = await import(`/src/components/feed/${name}.svelte`);
    window.fixtureProps = props;
    window.fixture = createClassComponent({ component: Component, target: document.querySelector('#fixture'), props });
    window.fixture.$on('toggleDescription', () => {
      const post = props.post || props.posts[0];
      const updated = { ...post, showFullDescription: !post.showFullDescription };
      props = name === 'PostCard' ? { ...props, post: updated } : { ...props, posts: [updated] };
      window.fixture.$set(props);
    });
  }, { name, props });
}

const event = {
  id: 'test-1', compositeId: 'test-1', time: 'Sep 23 at 5:36 PM',
  type: 'Traffic collision involving multiple vehicles',
  location: 'Interstate 5 southbound near Main Street offramp and the adjacent intersection',
  description: 'Reported details with enough text to require expansion. '.repeat(10),
  comments: [], likes: 0, active: false,
};

test('ticker keeps complete supplied headline fields', async ({ page }) => {
  await mountComponent(page, 'HeadlineTicker', { events: [event] });
  await expect(page.locator('.ticker-group').first().locator('.ticker-type')).toHaveText(event.type.toUpperCase());
  await expect(page.locator('.ticker-group').first().locator('.ticker-desc')).toHaveText(event.location.toUpperCase());
});

test('touch hover cannot freeze ticker and label has its own viewport', async ({ page, browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, baseURL: test.info().project.use.baseURL });
  const mobile = await context.newPage();
  await mountComponent(mobile, 'HeadlineTicker', { events: [event, { ...event, id: 'test-2' }] });
  const track = mobile.locator('.ticker-track');
  await mobile.locator('.ticker-content').tap();
  const state = await track.evaluate(el => getComputedStyle(el).animationPlayState);
  expect(state).toBe('running');
  const before = await track.evaluate(el => getComputedStyle(el).transform);
  await mobile.waitForTimeout(150);
  expect(await track.evaluate(el => getComputedStyle(el).transform)).not.toBe(before);
  const label = await mobile.locator('.ticker-label').boundingBox();
  const content = await mobile.locator('.ticker-content').boundingBox();
  expect(content.x).toBeGreaterThanOrEqual(label.x + label.width - 1);
  expect(content.x + content.width).toBeLessThanOrEqual(391);
  const widths = await track.evaluate(el => [el.getBoundingClientRect().width, ...[...el.children].map(c => c.getBoundingClientRect().width)]);
  expect(Math.abs(widths[0] - widths[1] - widths[2])).toBeLessThan(1);
  await context.close();
});

test('empty ticker recovers on data arrival and short loops cover the viewport', async ({ page }) => {
  await mountComponent(page, 'HeadlineTicker', { events: [] });
  await expect(page.locator('.ticker-wrapper')).toBeHidden();
  await page.evaluate(() => window.fixture.$set({ events: [{ time: 'Now', type: 'Hazard', location: 'Main St' }] }));
  await expect(page.locator('.ticker-wrapper')).toBeVisible();
  const content = await page.locator('.ticker-content').boundingBox();
  const group = await page.locator('.ticker-group').first().boundingBox();
  expect(group.width).toBeGreaterThanOrEqual(content.width - 1);
  const track = page.locator('.ticker-track');
  const loop = await track.evaluate(el => {
    const animation = el.getAnimations()[0];
    animation.pause();
    animation.currentTime = 0;
    const start = el.children[0].getBoundingClientRect().x;
    animation.currentTime = 44999;
    return { start, end: el.children[1].getBoundingClientRect().x };
  });
  expect(Math.abs(loop.start - loop.end)).toBeLessThan(1);
  await page.evaluate(() => window.fixture.$set({ events: [{ time: 'Later', type: 'Updated', location: 'New fetched location' }] }));
  await expect(page.locator('.ticker-group').first()).toContainText('NEW FETCHED LOCATION');
});

test('reduced motion keeps every headline reachable without animation', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await mountComponent(page, 'HeadlineTicker', { events: [event, { ...event, id: 'last', location: 'Final actual location' }] });
  const content = page.locator('.ticker-content');
  await expect(content).toHaveAttribute('tabindex', '0');
  expect(await content.evaluate(el => getComputedStyle(el).overflowX)).toBe('auto');
  expect(await page.locator('.ticker-track').evaluate(el => getComputedStyle(el).animationName)).toBe('none');
  await expect(page.locator('.ticker-group[aria-hidden="true"]')).toBeHidden();
  await content.evaluate(el => { el.scrollLeft = el.scrollWidth; });
  await expect(page.getByText('FINAL ACTUAL LOCATION', { exact: true }).first()).toBeInViewport();
});

for (const name of ['PostCard', 'PostTable']) {
  test(`${name} description control remains right aligned and accessible in both states`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const positions = [];
    const post = { ...event, showFullDescription: false };
    await mountComponent(page, name, name === 'PostCard' ? { post, animateFeedEntrance: false } : { posts: [post], expandedPostId: post.id, animateFeedEntrance: false });
    const button = page.locator('.more-button');
    for (const expanded of [false, true, false]) {
      await expect(button).toHaveAttribute('aria-expanded', String(expanded));
      await expect(button).toHaveAccessibleName(expanded ? /collapse description/i : /expand description/i);
      const bounds = await button.boundingBox();
      const parent = await page.locator('.description-text').boundingBox();
      expect(Math.abs(bounds.x + bounds.width - parent.x - parent.width)).toBeLessThan(1);
      expect(bounds.width).toBeGreaterThanOrEqual(44);
      positions.push(bounds.x);
      await button.focus();
      await expect(button).toBeFocused();
      await button.press(expanded ? "Space" : "Enter");
    }
    expect(Math.abs(positions[0] - positions[1])).toBeLessThan(1);
  });
}
