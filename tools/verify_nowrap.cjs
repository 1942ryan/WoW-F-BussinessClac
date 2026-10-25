// 验证：各视口宽度下是否还有「不该换行却换行」的单元格；确认态操作列是否溢出
const { chromium } = require('playwright');

const SIZES = process.argv.slice(2).length
  ? process.argv.slice(2).map((s) => s.split('x').map(Number))
  : [[1920, 1080], [1600, 900], [1536, 864], [1440, 900], [1366, 768]];

(async () => {
  const browser = await chromium.launch();
  for (const [W, H] of SIZES) {
    const ctx = await browser.newContext({ viewport: { width: W, height: H } });
    const page = await ctx.newPage();
    await page.goto('http://127.0.0.1:8787/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(800);
    await page.locator('button:has-text("PVP")').first().click();
    await page.locator('button:has-text("联盟")').first().click();
    const enter = page.locator('button').filter({ hasText: /创建|使用|开始/ }).first();
    if (await enter.count()) { await enter.click(); await page.waitForTimeout(1000); }
    await page.locator('.prof-card').filter({ hasText: '锻造' }).first().click();
    await page.waitForTimeout(2000);
    const calc = page.locator('button', { hasText: '计算路线' }).first();
    if (await calc.count()) { await calc.click(); await page.waitForTimeout(2000); }

    // 点第一行的星标（确认采用），检查操作列是否溢出
    await page.locator('.plan-recipes tbody tr').first().locator('td.op-col .icon-btn').last().click();
    await page.waitForTimeout(1200);

    const r = await page.evaluate(() => {
      const singleWrap = [];
      const prodWrap = [];
      document.querySelectorAll('.plan-recipes tbody tr').forEach((tr, i) => {
        const matCell = tr.cells[1];
        const rows = matCell ? matCell.querySelectorAll(':scope > .flex') : [];
        if (rows.length === 1 && rows[0].getBoundingClientRect().height > 26) {
          singleWrap.push({ i, text: rows[0].textContent.trim().slice(0, 14), h: Math.round(rows[0].getBoundingClientRect().height) });
        }
        // 成品列：看 .prod-line 是不是被挤成多行
        const line = tr.cells[0] && tr.cells[0].querySelector('.prod-line');
        if (line) {
          const rng = document.createRange();
          rng.selectNodeContents(line);
          const tops = [...rng.getClientRects()].filter((x) => x.width > 0).map((x) => x.top).sort((a, b) => a - b);
          let n = 0;
          let last = -1e9;
          for (const t of tops) {
            if (t - last > 8) n += 1;
            last = t;
          }
          if (n > 1) prodWrap.push({ i, lines: n });
        }
      });
      const op = document.querySelector('.plan-recipes tbody td.op-col');
      const opR = op.getBoundingClientRect();
      const kids = [...op.children].map((c) => Math.round(c.getBoundingClientRect().right));
      const scroll = document.querySelector('.table-scroll');
      return {
        singleWrapCount: singleWrap.length,
        singleWrapSample: singleWrap.slice(0, 3),
        prodWrapCount: prodWrap.length,
        opW: Math.round(opR.width),
        opContentRight: Math.max(...kids) - Math.round(opR.left),
        opOverflow: Math.max(...kids) > Math.round(opR.right) + 1,
        tableScroll: { cw: scroll.clientWidth, sw: scroll.scrollWidth },
        docW: document.documentElement.scrollWidth,
      };
    });
    console.log(
      `${W}x${H} | 单材料换行 ${r.singleWrapCount} | 成品格过高 ${r.prodWrapCount} | 操作列 ${r.opW}px 内容右缘 ${r.opContentRight} 溢出=${r.opOverflow} | 表 ${r.tableScroll.cw}→${r.tableScroll.sw}`,
    );
    if (r.singleWrapSample.length) console.log('   例:', JSON.stringify(r.singleWrapSample));
    await page.screenshot({ path: `verify-${W}.png` });
    await ctx.close();
  }
  await browser.close();
})();
