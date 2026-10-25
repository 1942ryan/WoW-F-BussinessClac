// 放大截取某个单元格，检查颜色/对比度
const { chromium } = require('playwright');
const OUT = process.argv[2] || 'cell.png';
const SEL = process.argv[3] || '.plan-recipes tbody tr:first-child td:nth-child(6)';
const SCALE = Number(process.argv[4] || 4);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: SCALE });
  await page.goto('http://127.0.0.1:8787/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(900);
  await page.locator('button:has-text("PVP")').first().click();
  await page.locator('button:has-text("联盟")').first().click();
  const enter = page.locator('button').filter({ hasText: /创建|使用|开始/ }).first();
  if (await enter.count()) { await enter.click(); await page.waitForTimeout(1200); }
  await page.locator('.prof-card').filter({ hasText: '锻造' }).first().click();
  await page.waitForTimeout(2200);
  const calc = page.locator('button', { hasText: '计算路线' }).first();
  if (await calc.count()) { await calc.click(); await page.waitForTimeout(2200); }
  const el = page.locator(SEL).first();
  await el.screenshot({ path: OUT });
  const style = await el.evaluate((n) => {
    const t = n.querySelector('.tag') || n;
    const cs = getComputedStyle(t);
    return { text: t.textContent.trim(), color: cs.color, bg: cs.backgroundColor, cls: t.className };
  });
  console.log(JSON.stringify(style, null, 2));
  await browser.close();
})();
