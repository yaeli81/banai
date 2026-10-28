import { expect, test } from './fixtures.js';

const design = (page) => page.evaluate(() => window.__banai.store.getState().design);

test.describe('starting templates on the start screen', () => {
  test('the start screen lists three templates under the entry cards', async ({ page }) => {
    await page.goto('/');
    const list = page.getByRole('region', { name: 'Or start from a template' });
    await expect(list.getByRole('button')).toHaveCount(3);
    await expect(page.getByTestId('preset-kids')).toContainText("Kids' wardrobe");
    await expect(page.getByTestId('preset-kids')).toContainText('150 × 180 × 55 cm');
  });

  for (const [id, dimensions, doorType, meshId] of [
    ['kids', { width: 1500, height: 1800, depth: 550 }, 'hinged', 'rail_kids'],
    ['sliding', { width: 2400, height: 2400, depth: 650 }, 'sliding', 'dr_slide1'],
    ['minimal', { width: 1200, height: 2200, depth: 600 }, 'hinged', 'shf_min1'],
  ]) {
    test(`choosing "${id}" opens that template in the editor and the 3D view`, async ({ page }) => {
      await page.goto('/');
      await page.getByTestId(`preset-${id}`).click();
      await expect(page.getByTestId('start-screen')).toHaveCount(0);
      await page.waitForFunction((mesh) => window.__banai?.viewer.meshOf(mesh), meshId);
      const opened = await design(page);
      expect(opened.dimensions).toEqual(dimensions);
      expect(opened.doors.type).toBe(doorType);
      expect(await page.evaluate(() => window.__banai.store.getState().revision)).toBe(2);
      await expect(page.locator('#properties-panel')).toBeFocused();
    });
  }

  test('a template can be edited like any design', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('preset-minimal').click();
    await page.waitForFunction(() => window.__banai?.viewer.meshOf('shf_min1'));
    const result = await page.evaluate(() => window.__banai.store.dispatch([{ op: 'remove_component', id: 'shf_min1' }]));
    expect(result.ok).toBe(true);
    expect((await design(page)).compartments[1].shelves).toHaveLength(2);
  });
});
