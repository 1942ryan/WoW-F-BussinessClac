// 悬停物品图标 → 抓「游戏内风格」tooltip 文案 + 截图（含硬币图标清晰度检查）
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1600, height: 900 },
    deviceScaleFactor: 2, // 模拟 HiDPI，检查硬币是否还发糊
  });
  const page = await ctx.newPage();
  await page.goto('http://127.0.0.1:8787/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);
  await page.locator('button:has-text("PVP")').first().click();
  await page.locator('button:has-text("联盟")').first().click();
  const enter = page.locator('button').filter({ hasText: /创建|使用|开始/ }).first();
  if (await enter.count()) { await enter.click(); await page.waitForTimeout(800); }
  await page.locator('.prof-card').filter({ hasText: '制皮' }).first().click();
  await page.waitForTimeout(2200);
  const calcBtn = page.locator('button', { hasText: '计算路线' }).first();
  if (await calcBtn.count()) { await calcBtn.click(); await page.waitForTimeout(2200); }

  // 优先找一件装备类成品（带护甲值/属性/需要等级的完整 tooltip）
  const rows = page.locator('.plan-recipes tbody tr');
  const n = await rows.count();
  let target = null;
  for (let i = 0; i < n; i++) {
    const icon = rows.nth(i).locator('td').first().locator('.ic-wrap').first();
    if (!(await icon.count())) continue;
    await icon.hover({ force: true });
    await page.waitForTimeout(900);
    const text = await page.evaluate(() => {
      const el = document.querySelector('.item-tip');
      return el ? el.innerText : '';
    });
    if (text.includes('需要等级')) { target = icon; break; }
  }
  if (!target) target = rows.first().locator('td').first().locator('.ic-wrap').first();
  await target.hover({ force: true });
  await page.waitForTimeout(1000);

  const info = await page.evaluate(() => {
    const el = document.querySelector('.item-tip');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { text: el.innerText, x: r.x, y: r.y, w: r.width, h: r.height };
  });
  console.log(info ? info.text : '(tooltip 没出现)');
  if (info) {
    await page.screenshot({
      path: 'shot-tooltip.png',
      clip: {
        x: Math.max(0, info.x - 24),
        y: Math.max(0, info.y - 24),
        width: Math.min(1500, info.w + 90),
        height: Math.min(880, info.h + 60),
      },
    });
    console.log(`尺寸 ${Math.round(info.w)}×${Math.round(info.h)}`);
  }
  // 顺带拍一张结果区（看硬币图标）
  await page.mouse.move(10, 10);
  await page.waitForTimeout(400);
  const card = page.locator('.summary-cards').first();
  if (await card.count()) {
    await card.screenshot({ path: 'shot-coins.png' });
  }
  await browser.close();
})();
