// 在 1920×1080 下测量规划页各列几何，找出折行/溢出的元素
const { chromium } = require('playwright');

const OUT = process.argv[2] || '.';
const W = Number(process.argv[3] || 1920);
const H = Number(process.argv[4] || 1080);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.goto('http://127.0.0.1:8787/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);

  // 选服务器 + 阵营 → 创建/使用
  await page.locator('button:has-text("PVP")').first().click();
  await page.locator('button:has-text("联盟")').first().click();
  const enter = page.locator('button').filter({ hasText: /创建|使用|开始/ }).first();
  if (await enter.count()) {
    await enter.click();
    await page.waitForTimeout(1500);
  }

  // 点「锻造」卡片进规划页（会带上 professionKey）
  await page.locator('.prof-card').filter({ hasText: '锻造' }).first().click();
  await page.waitForTimeout(2500);
  // 点一次「计算路线」把结果算出来
  const calc = page.locator('button', { hasText: '计算路线' }).first();
  if (await calc.count()) {
    await calc.click();
    await page.waitForTimeout(2500);
  }
  console.log('URL:', page.url());
  await page.screenshot({ path: `${OUT}/p2-plan-${W}.png`, fullPage: false });

  const data = await page.evaluate(() => {
    const pick = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { w: Math.round(r.width), h: Math.round(r.height), x: Math.round(r.x), y: Math.round(r.y) };
    };
    const wrap = document.querySelector('.plan-body');
    const cols = wrap ? [...wrap.children].map((c) => {
      const r = c.getBoundingClientRect();
      return { cls: c.className, w: Math.round(r.width), h: Math.round(r.height) };
    }) : [];

    // 表格：哪些单元格内容换行了
    const wrappedCells = [];
    document.querySelectorAll('.plan-body table').forEach((tb, ti) => {
      tb.querySelectorAll('th, td').forEach((c) => {
        const cs = getComputedStyle(c);
        const lh = parseFloat(cs.lineHeight) || 16;
        const lines = Math.round(c.getBoundingClientRect().height / lh);
        if (lines > 1 || c.scrollWidth > c.clientWidth + 1) {
          wrappedCells.push({
            table: ti,
            tag: c.tagName,
            text: (c.textContent || '').trim().slice(0, 18),
            h: Math.round(c.getBoundingClientRect().height),
            lines,
            overflow: c.scrollWidth - c.clientWidth,
          });
        }
      });
    });

    return {
      viewport: { w: innerWidth, h: innerHeight },
      docWidth: document.documentElement.scrollWidth,
      bodyOverflowX: document.documentElement.scrollWidth > innerWidth,
      bars: { topbar: pick('.topbar'), plan: pick('.plan-body') },
      cols,
      wrappedCount: wrappedCells.length,
      wrapped: wrappedCells.slice(0, 20),
    };
  });
  console.log(JSON.stringify(data, null, 2));

  await browser.close();
})();
