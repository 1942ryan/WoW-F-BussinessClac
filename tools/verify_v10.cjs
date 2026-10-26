// 本轮改动验证：AH 到手价显示 / 按卖店标记 / 确认数量默认值 / 分享链接直达
const { chromium } = require('playwright');

async function enterPlan(page, prof) {
  await page.goto('http://127.0.0.1:8787/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(700);
  // 已有服务器列表：点第一个「PVP服」（both）
  await page.locator('button:has-text("PVP")').first().click();
  const f = page.locator('button:has-text("联盟")').first();
  if (await f.count()) await f.click();
  const enter = page.locator('button').filter({ hasText: /创建|使用|开始/ }).first();
  if (await enter.count()) { await enter.click(); await page.waitForTimeout(900); }
  await page.locator('.prof-card').filter({ hasText: prof }).first().click();
  await page.waitForTimeout(2600);
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();

  await enterPlan(page, '工程学');
  const rows = await page.locator('.plan-recipes tbody tr').count();
  console.log('工程学配方行数:', rows);
  console.log('按卖店标记:', await page.locator('.plan-recipes .tag.npc').count());
  console.log('AH无价标签:', await page.locator('.plan-recipes .tag.noah').count());
  console.log('CD 标签:', await page.locator('.plan-recipes .tag.cd').count());

  // 拍卖行按钮里的价格是否已是到手价（与 product_ah_net 对照）
  const check = await page.evaluate(() => {
    const tr = document.querySelector('.plan-recipes tbody tr');
    if (!tr) return null;
    const btns = tr.querySelectorAll('.price-btn');
    return [...btns].map((b) => b.textContent.replace(/\s+/g, ' ').trim());
  });
  console.log('首行处置按钮:', JSON.stringify(check));

  // 非 CD 配方 → 确认默认「不限」
  const firstStar = page.locator('.plan-recipes tbody tr').first().locator('td.op-col .icon-btn').last();
  await firstStar.click();
  await page.waitForTimeout(1300);
  const cnt = await page.evaluate(() => {
    const el = document.querySelector('.cnt-input');
    return el ? { value: el.value, placeholder: el.placeholder } : null;
  });
  console.log('非 CD 确认后次数框:', JSON.stringify(cnt));

  // 有「按卖店」的行截图
  const npcTag = page.locator('.plan-recipes .tag.npc').first();
  if (await npcTag.count()) {
    const row = page.locator('.plan-recipes tbody tr').filter({ has: npcTag }).first();
    await row.scrollIntoViewIfNeeded();
    const box = await row.boundingBox();
    await page.screenshot({ path: 'v10-npc-better.png', clip: {
      x: Math.max(0, box.x), y: Math.max(0, box.y - 34), width: 1180, height: 120 } });
  } else {
    await page.screenshot({ path: 'v10-npc-better.png', clip: { x: 0, y: 0, width: 1180, height: 300 } });
  }

  // CD 配方（裁缝·月布）默认 1
  await enterPlan(page, '裁缝');
  const cdRow = page.locator('.plan-recipes tbody tr').filter({ hasText: /^月布/ }).first();
  const cdTagRow = page.locator('.plan-recipes tbody tr').filter({ has: page.locator('.tag.cd') }).first();
  const target = (await cdRow.count()) ? cdRow : cdTagRow;
  if (await target.count()) {
    await target.scrollIntoViewIfNeeded();
    await target.locator('td.op-col .icon-btn').last().click();
    await page.waitForTimeout(1300);
    console.log('CD 配方确认后次数:', await target.locator('.cnt-input').inputValue());
    const box = await target.boundingBox();
    await page.screenshot({ path: 'v10-cd-count.png', clip: {
      x: Math.max(0, box.x), y: Math.max(0, box.y - 34), width: 1180, height: 110 } });
  } else {
    console.log('没找到 CD 配方行');
  }

  // 保存 → 分享链接 → 打开
  const calcBtn = page.locator('button', { hasText: '计算路线' }).first();
  if (await calcBtn.count()) { await calcBtn.click(); await page.waitForTimeout(2600); }
  const saveBtn = page.locator('button', { hasText: '保存 / 分享这条路线' }).first();
  if (await saveBtn.count()) {
    await saveBtn.scrollIntoViewIfNeeded();
    await saveBtn.click();
    await page.waitForTimeout(600);
    await page.locator('.save-dialog input[type="text"]').first().fill('自动化验证路线');
    await page.locator('.save-dialog button', { hasText: '保存' }).first().click();
    await page.waitForTimeout(1800);
    const link = await page.locator('.save-dialog input[type="text"]').first().inputValue().catch(() => '');
    console.log('分享链接:', link);
    await page.screenshot({ path: 'v10-share-dialog.png' });
    if (link) {
      const p2 = await ctx.newPage();
      await p2.goto(link, { waitUntil: 'networkidle' });
      await p2.waitForTimeout(1600);
      await p2.screenshot({ path: 'v10-share-page.png' });
      const t = await p2.locator('h2').first().innerText().catch(() => '');
      console.log('分享页标题:', t.replace(/\n/g, ' '));
      await p2.close();
    }
  } else {
    console.log('没找到保存按钮（可能未算出结果）');
  }

  await browser.close();
})();
