// 截图 v11：文字悬停 tooltip / 价格有效期一行 / 来源浮层「出没」/ 导价教程页
const { chromium } = require('playwright');

const SESSION = {
  serverId: 1,
  serverName: 'PVP服',
  serverFaction: 'both',
  professionKey: 'engineering',
  fromSkill: 1,
  toSkill: 300,
  priceMode: 'latest',
  blockedRecipeIds: [],
  blockedItemIds: [],
  confirmedRecipeIds: [],
  confirmedCounts: {},
  recipeDispositions: {},
};

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 }, deviceScaleFactor: 2 });
  await ctx.addInitScript((s) => {
    localStorage.setItem('wowfc-session-v2', JSON.stringify(s));
  }, SESSION);
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.log('PAGE ERROR:', e.message));

  await page.goto('http://127.0.0.1:8787/plan', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2200);

  // 1) 价格有效期一行
  const fresh = page.locator('.fresh-row');
  console.log('fresh-row:', (await fresh.innerText()).replace(/\s+/g, ' '));
  const fb = await fresh.boundingBox();
  await page.screenshot({ path: 'v11-freshness.png', clip: {
    x: Math.max(0, fb.x - 4), y: Math.max(0, fb.y - 6), width: Math.min(1200, fb.width + 12), height: fb.height + 12 } });

  // 2) 悬停「材料名字」文字（不是图标）应弹出物品卡
  const matText = page.locator('.plan-recipes td.wrap .ic-text span').first();
  const mtxt = await matText.innerText();
  await matText.hover();
  await page.waitForTimeout(1200);
  const tip = page.locator('.item-tip');
  const tipCount = await tip.count();
  console.log('悬停文字:', mtxt, '→ tooltip 数量:', tipCount);
  if (tipCount) {
    console.log('tooltip 内容:', (await tip.innerText()).replace(/\s+/g, ' ').slice(0, 200));
    const tb = await tip.boundingBox();
    await page.screenshot({ path: 'v11-text-tooltip.png', clip: {
      x: Math.max(0, tb.x - 30), y: Math.max(0, tb.y - 60), width: 520, height: Math.min(560, tb.height + 100) } });
  }

  await page.mouse.move(5, 5);
  await page.waitForTimeout(400);

  // 3) 来源浮层：找一条 source_detail 带「出没」的配方
  const rows = page.locator('.plan-recipes tbody tr');
  const n = await rows.count();
  let done = false;
  for (let i = 0; i < n && !done; i++) {
    const cell = rows.nth(i).locator('.src-cell');
    if (!(await cell.count())) continue;
    await cell.hover();
    await page.waitForTimeout(350);
    const st = page.locator('.src-tip');
    if ((await st.count()) && (await st.innerText()).includes('出没')) {
      console.log('来源浮层(出没):', (await st.innerText()).replace(/\s+/g, ' '));
      const b = await st.boundingBox();
      await page.screenshot({ path: 'v11-source-tip.png', clip: {
        x: Math.max(0, b.x - 12), y: Math.max(0, b.y - 12), width: b.width + 24, height: b.height + 24 } });
      done = true;
    }
    await page.mouse.move(5, 5);
    await page.waitForTimeout(120);
  }
  console.log('找到带「出没」的来源浮层:', done);

  // 4) 导价教程页
  await page.goto('http://127.0.0.1:8787/guide', { waitUntil: 'networkidle' });
  await page.waitForTimeout(800);
  await page.screenshot({ path: 'v11-guide-top.png' });
  await page.evaluate(() => window.scrollTo(0, 900));
  await page.waitForTimeout(400);
  await page.screenshot({ path: 'v11-guide-step.png' });

  await browser.close();
})();
