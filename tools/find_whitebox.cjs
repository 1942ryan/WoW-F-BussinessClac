// 找出页面里宽度 50~65、高度 15~25 的元素（疑似用户截图里的白色小方块）
const { chromium } = require('playwright');

(async () => {
  const [W, H] = (process.argv[2] || '1366x768').split('x').map(Number);
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: W, height: H } });
  const page = await ctx.newPage();
  await page.goto('http://127.0.0.1:8787/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);
  await page.locator('button:has-text("PVP")').first().click();
  await page.locator('button:has-text("联盟")').first().click();
  const enter = page.locator('button').filter({ hasText: /创建|使用|开始/ }).first();
  if (await enter.count()) { await enter.click(); await page.waitForTimeout(800); }
  await page.locator('.prof-card').filter({ hasText: '锻造' }).first().click();
  await page.waitForTimeout(2000);

  const list = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('.plan-recipes *').forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width >= 48 && r.width <= 70 && r.height >= 14 && r.height <= 26) {
        const cs = getComputedStyle(el);
        out.push({
          tag: el.tagName,
          cls: (el.className || '').toString().slice(0, 40),
          w: Math.round(r.width),
          h: Math.round(r.height),
          bg: cs.backgroundColor,
          x: Math.round(r.x),
          y: Math.round(r.y),
        });
      }
    });
    return out;
  });
  console.log(JSON.stringify(list.slice(0, 40), null, 1));
  await browser.close();
})();
