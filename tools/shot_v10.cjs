// 截图：按卖店标记 / 营地来源浮层（精简后）
const { chromium } = require('playwright');

const SESSION = {
  serverId: 1,
  serverName: 'PVP服',
  serverFaction: 'both',
  professionKey: 'first-aid',
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

  await page.goto('http://127.0.0.1:8787/plan', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2600);

  const tag = page.locator('.plan-recipes .tag.npc').first();
  const n = await page.locator('.plan-recipes .tag.npc').count();
  console.log('急救「按卖店」标记数:', n);
  if (n) {
    const row = page.locator('.plan-recipes tbody tr:has(.tag.npc)').first();
    await row.scrollIntoViewIfNeeded();
    const b = await row.boundingBox();
    await page.screenshot({ path: 'v10-npc-better.png', clip: {
      x: Math.max(0, b.x), y: Math.max(0, b.y - 36), width: 1150, height: 118 } });
    const txt = await row.evaluate((el) => el.innerText.replace(/\s+/g, ' '));
    console.log('行内容:', txt);
  }

  // 营地来源浮层（工程学 · 切专业）
  const eng = page.locator('.prof-card').filter({ hasText: '工程学' }).first();
  if (await eng.count()) {
    await eng.click();
    await page.waitForTimeout(2600);
    const camp = page.locator('.plan-recipes .tag.camp').first();
    if (await camp.count()) {
      await camp.scrollIntoViewIfNeeded();
      await camp.hover();
      await page.waitForTimeout(1000);
      const info = await page.evaluate(() => {
        const el = document.querySelector('.src-tip');
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { text: el.innerText, x: r.x, y: r.y, w: r.width, h: r.height };
      });
      console.log('浮层文案:\n' + (info ? info.text : '(未出现)'));
      if (info) {
        await page.screenshot({ path: 'v10-camp-tip.png', clip: {
          x: Math.max(0, info.x - 12), y: Math.max(0, info.y - 12),
          width: info.w + 30, height: info.h + 26 } });
      }
    } else {
      console.log('没找到营地标签');
    }
  }

  await browser.close();
})();
