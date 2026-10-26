// 复现：配方列表里出现的白色矩形遮挡（用户截图红框处）
const { chromium } = require('playwright');

(async () => {
  const W = Number(process.argv[2] || 1366);
  const H = Number(process.argv[3] || 768);
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto('http://127.0.0.1:8787/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(700);
  await page.locator('button:has-text("PVP")').first().click();
  await page.locator('button:has-text("联盟")').first().click();
  const enter = page.locator('button').filter({ hasText: /创建|使用|开始/ }).first();
  if (await enter.count()) { await enter.click(); await page.waitForTimeout(900); }
  await page.locator('.prof-card').filter({ hasText: '锻造' }).first().click();
  await page.waitForTimeout(2200);
  const calc = page.locator('button', { hasText: '计算路线' }).first();
  if (await calc.count()) { await calc.click(); await page.waitForTimeout(1800); }

  // 滚到「银触媒」附近
  const row = page.locator('.plan-recipes tbody tr').filter({ hasText: '银触媒' }).first();
  if (await row.count()) await row.scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);

  const box = await page.locator('.table-scroll').boundingBox();
  await page.screenshot({ path: `bug-${W}.png`, clip: box });

  // 列出该行每个单元格里、背景是白色的元素
  const info = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('.plan-recipes tbody tr').forEach((tr, i) => {
      tr.querySelectorAll('*').forEach((el) => {
        const cs = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        if (r.width > 8 && r.height > 8 && /rgb\(255,\s*255,\s*255\)/.test(cs.backgroundColor)) {
          out.push({ row: i, cls: el.className && el.className.toString(), tag: el.tagName, w: Math.round(r.width), h: Math.round(r.height), x: Math.round(r.x) });
        }
      });
    });
    return out.slice(0, 30);
  });
  console.log(JSON.stringify(info, null, 1));
  await browser.close();
})();
