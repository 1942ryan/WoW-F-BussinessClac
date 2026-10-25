// 验证来源列悬停浮层能显示「出处」
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
  await page.goto('http://127.0.0.1:8787/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(800);
  await page.locator('button:has-text("PVP")').first().click();
  await page.locator('button:has-text("联盟")').first().click();
  const enter = page.locator('button').filter({ hasText: /创建|使用|开始/ }).first();
  if (await enter.count()) { await enter.click(); await page.waitForTimeout(1000); }
  await page.locator('.prof-card').filter({ hasText: '锻造' }).first().click();
  await page.waitForTimeout(2200);

  // 找一行是「设计图」来源的
  const target = page.locator('.plan-recipes tbody tr', { has: page.locator('span.tag.design') }).first();
  const cell = target.locator('td').nth(5).locator('.src-cell');
  await cell.scrollIntoViewIfNeeded();
  await cell.hover({ force: true });
  await page.waitForTimeout(700);

  const tip = await page.evaluate(() => {
    const el = [...document.querySelectorAll('div')].find(
      (d) => getComputedStyle(d).position === 'fixed' && d.textContent.includes('出处'),
    );
    return el ? el.innerText : null;
  });
  console.log('浮层内容：\n' + (tip || '(没抓到)'));
  await page.screenshot({ path: 'hover-src.png', clip: { x: 300, y: 300, width: 900, height: 420 } });
  await browser.close();
})();
