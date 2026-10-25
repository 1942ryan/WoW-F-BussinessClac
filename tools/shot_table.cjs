// 截图配方表首屏，便于肉眼确认折行位置
const { chromium } = require('playwright');
const W = Number(process.argv[2] || 1920);
const H = Number(process.argv[3] || 1080);
const OUT = process.argv[4] || `table-${W}.png`;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.goto('http://127.0.0.1:8787/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(900);
  await page.locator('button:has-text("PVP")').first().click();
  await page.locator('button:has-text("联盟")').first().click();
  const enter = page.locator('button').filter({ hasText: /创建|使用|开始/ }).first();
  if (await enter.count()) {
    await enter.click();
    await page.waitForTimeout(1200);
  }
  await page.locator('.prof-card').filter({ hasText: '锻造' }).first().click();
  await page.waitForTimeout(2200);
  const calc = page.locator('button', { hasText: '计算路线' }).first();
  if (await calc.count()) {
    await calc.click();
    await page.waitForTimeout(2200);
  }
  const el = await page.$('.plan-recipes');
  await el.screenshot({ path: OUT });
  // 顺便把单材料却换行的行数统计出来
  const stat = await page.evaluate(() => {
    let singleWrapped = 0;
    let singleTotal = 0;
    document.querySelectorAll('.plan-recipes tbody tr').forEach((tr) => {
      const cell = tr.cells[1];
      if (!cell) return;
      const mats = cell.querySelectorAll('.mat-row, .wrap > span, .wrap > div');
      const n = cell.querySelectorAll('.mat-row').length;
      if (n === 1) {
        singleTotal += 1;
        const h = cell.getBoundingClientRect().height;
        if (h > 34) singleWrapped += 1;
      }
    });
    return { singleWrapped, singleTotal };
  });
  console.log(JSON.stringify(stat));
  await browser.close();
})();
