// 决定性实验：悬停「营地 N」标签与技能档列，看页面内是否会出现白色方块
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto('http://127.0.0.1:8787/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(700);
  await page.locator('button:has-text("PVP")').first().click();
  await page.locator('button:has-text("联盟")').first().click();
  const enter = page.locator('button').filter({ hasText: /创建|使用|开始/ }).first();
  if (await enter.count()) { await enter.click(); await page.waitForTimeout(900); }
  await page.locator('.prof-card').filter({ hasText: '工程学' }).first().click();
  await page.waitForTimeout(2200);

  const camp = page.locator('.plan-recipes .tag.camp').first();
  if (await camp.count()) {
    await camp.scrollIntoViewIfNeeded();
    const b = await camp.boundingBox();
    await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
    await page.waitForTimeout(1200);
    await page.screenshot({ path: 'hover-camp.png', clip: {
      x: Math.max(0, b.x - 340), y: Math.max(0, b.y - 120), width: Math.min(700, 1200), height: 300 } });
    // 检查页面里有没有白底且无文本的小方块
    const whites = await page.evaluate(() => {
      const out = [];
      document.querySelectorAll('body *').forEach((el) => {
        const cs = getComputedStyle(el);
        if (cs.backgroundColor !== 'rgb(255, 255, 255)') return;
        const r = el.getBoundingClientRect();
        if (r.width < 40 || r.width > 90 || r.height < 12 || r.height > 26) return;
        out.push({ tag: el.tagName, cls: (el.className || '').toString().slice(0, 30), w: Math.round(r.width), h: Math.round(r.height), t: (el.textContent || '').trim().slice(0, 12) });
      });
      return out;
    });
    console.log('white boxes:', JSON.stringify(whites));
  } else {
    console.log('没找到营地标签');
  }
  await browser.close();
})();
