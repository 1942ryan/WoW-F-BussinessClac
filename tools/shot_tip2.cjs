const { chromium } = require('playwright');
(async () => {
  const name = process.argv[2] || '雕花皮靴';
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto('http://127.0.0.1:8787/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);
  await page.locator('button:has-text("PVP")').first().click();
  await page.locator('button:has-text("联盟")').first().click();
  const enter = page.locator('button').filter({ hasText: /创建|使用|开始/ }).first();
  if (await enter.count()) { await enter.click(); await page.waitForTimeout(800); }
  await page.locator('.prof-card').filter({ hasText: '制皮' }).first().click();
  await page.waitForTimeout(2200);
  const row = page.locator('.plan-recipes tbody tr').filter({ hasText: name }).first();
  await row.scrollIntoViewIfNeeded();
  const icon = row.locator('td').first().locator('.ic-wrap').first();
  await icon.hover({ force: true });
  await page.waitForTimeout(1100);
  const info = await page.evaluate(() => {
    const el = document.querySelector('.item-tip');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { text: el.innerText, x: r.x, y: r.y, w: r.width, h: r.height };
  });
  console.log(info ? info.text : '(没抓到)');
  if (info) await page.screenshot({ path: 'shot-tip2.png', clip: {
    x: Math.max(0, info.x - 20), y: Math.max(0, info.y - 20),
    width: info.w + 70, height: info.h + 50 } });
  await browser.close();
})();
