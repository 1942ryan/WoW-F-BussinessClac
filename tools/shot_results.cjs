// 1x DPI 下检查硬币图标与结果区排版（1080P 实际观感）
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto('http://127.0.0.1:8787/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);
  await page.locator('button:has-text("PVP")').first().click();
  await page.locator('button:has-text("联盟")').first().click();
  const enter = page.locator('button').filter({ hasText: /创建|使用|开始/ }).first();
  if (await enter.count()) { await enter.click(); await page.waitForTimeout(800); }
  await page.locator('.prof-card').filter({ hasText: '锻造' }).first().click();
  await page.waitForTimeout(2000);
  const calc = page.locator('button', { hasText: '计算路线' }).first();
  if (await calc.count()) { await calc.click(); await page.waitForTimeout(2500); }

  const panel = page.locator('.plan-results').first();
  if (await panel.count()) {
    await panel.screenshot({ path: 'shot-results-1x.png' });
    const note = await page.locator('.calc-note').first().innerText().catch(() => '(无)');
    console.log('口径说明：', note.replace(/\n/g, ' '));
  }
  // 硬币放大 8 倍看清楚轮廓
  const coin = page.locator('.summary-cards .coin').first();
  if (await coin.count()) {
    await coin.screenshot({ path: 'shot-coin-zoom.png', scale: 'css' });
  }
  await browser.close();
})();
