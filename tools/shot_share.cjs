const { chromium } = require('playwright');
(async () => {
  const code = process.argv[2];
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto(`http://127.0.0.1:8787/r/${code}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: 'v10-share-page2.png', fullPage: true });
  const h = await page.locator('h2').first().innerText();
  console.log('标题:', h.replace(/\s+/g, ' '));
  console.log('步骤行数:', await page.locator('table.grid').first().locator('tbody tr').count());
  await browser.close();
})();
