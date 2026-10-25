// 扫多个视口宽度，报告横向溢出与折行的关键元素
const { chromium } = require('playwright');

const SIZES = [
  [1920, 1080],
  [1600, 900],
  [1536, 864], // 1080p + 125% 缩放
  [1440, 810],
  [1366, 768],
  [1280, 720], // 1080p + 150% 缩放
];

(async () => {
  const browser = await chromium.launch();
  for (const [W, H] of SIZES) {
    const ctx = await browser.newContext({ viewport: { width: W, height: H } });
    const page = await ctx.newPage();
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

    const d = await page.evaluate(() => {
      const r = (el) => (el ? el.getBoundingClientRect() : null);
      const cols = [...(document.querySelector('.plan-body')?.children || [])].map((c) => ({
        cls: c.className,
        w: Math.round(r(c).width),
      }));
      // 找出所有横向溢出父容器的元素
      const overflow = [];
      document.querySelectorAll('.plan-recipes *').forEach((el) => {
        if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0) {
          overflow.push({
            cls: el.className,
            tag: el.tagName,
            sw: el.scrollWidth,
            cw: el.clientWidth,
            text: (el.textContent || '').trim().slice(0, 16),
          });
        }
      });
      // 关键表格列宽
      const tbl = document.querySelector('.plan-recipes table');
      const ths = tbl ? [...tbl.querySelectorAll('thead th')].map((th) => ({
        t: (th.textContent || '').trim().slice(0, 10),
        w: Math.round(r(th).width),
        top: Math.round(r(th).top),
      })) : [];
      const uniqueTops = [...new Set(ths.map((x) => x.top))];
      return {
        viewport: { w: innerWidth, h: innerHeight },
        docW: document.documentElement.scrollWidth,
        overflowX: document.documentElement.scrollWidth > innerWidth,
        cols,
        ths,
        headRows: uniqueTops.length,
        overflow: overflow.slice(0, 8),
      };
    });
    console.log(
      `${W}x${H} | 文档宽 ${d.docW} 横向溢出=${d.overflowX} | 列 ${d.cols.map((c) => c.w).join('/')} | 表头行数 ${d.headRows}`,
    );
    d.ths.forEach((t) => process.stdout.write(`    ${t.t}:${t.w}`));
    console.log('');
    d.overflow.forEach((o) => console.log(`    溢出 ${o.tag}.${o.cls} ${o.cw}→${o.sw} 「${o.text}」`));
    await page.screenshot({ path: `p-${W}.png` });
    await ctx.close();
  }
  await browser.close();
})();
