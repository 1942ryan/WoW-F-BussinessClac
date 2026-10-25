// 精确找出真正换行（多行盒）的单元格/元素
const { chromium } = require('playwright');

const W = Number(process.argv[2] || 1920);
const H = Number(process.argv[3] || 1080);

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

  const res = await page.evaluate(() => {
    // 统计元素内所有文本行的 top 值，>1 说明换行了
    // 行盒 top 做 8px 聚类（内联图标与文字基线不同，不聚类会误判）
    const lineCount = (el) => {
      const range = document.createRange();
      range.selectNodeContents(el);
      const tops = [...range.getClientRects()]
        .filter((r) => r.width > 0 && r.height > 0)
        .map((r) => r.top)
        .sort((a, b) => a - b);
      let n = 0;
      let last = -1e9;
      for (const t of tops) {
        if (t - last > 8) n += 1;
        last = t;
      }
      return n;
    };
    const rows = [];
    document.querySelectorAll('.plan-recipes thead th').forEach((el) => {
      rows.push({ kind: 'th', text: el.textContent.trim().slice(0, 14), lines: lineCount(el), w: Math.round(el.getBoundingClientRect().width) });
    });
    const tdSeen = new Map();
    document.querySelectorAll('.plan-recipes tbody td').forEach((el) => {
      const n = lineCount(el);
      if (n > 1) {
        const key = el.className || el.cellIndex;
        const cur = tdSeen.get(`${el.cellIndex}|${key}`) || { idx: el.cellIndex, cls: el.className, n: 0, sample: el.textContent.trim().slice(0, 20) };
        cur.n += 1;
        tdSeen.set(`${el.cellIndex}|${key}`, cur);
      }
    });
    // 非表格区域的换行（如计算参数按钮行）
    const others = [];
    document.querySelectorAll('.panel button, .panel label, .panel h2, .toolbar > *').forEach((el) => {
      if (el.closest('table')) return;
      if (lineCount(el) > 1) others.push({ tag: el.tagName, cls: el.className, text: el.textContent.trim().slice(0, 20) });
    });
    return {
      viewport: { w: innerWidth, h: innerHeight },
      ths: rows,
      tds: [...tdSeen.values()].sort((a, b) => b.n - a.n).slice(0, 10),
      others: others.slice(0, 10),
      tableScroll: (() => {
        const t = document.querySelector('.table-scroll');
        return t ? { cw: t.clientWidth, sw: t.scrollWidth } : null;
      })(),
    };
  });

  console.log(`==== ${W}x${H} ====`);
  console.log('表头行数:', res.ths.map((t) => `${t.text}=${t.lines}行/${t.w}px`).join('  '));
  console.log('换行单元格:', JSON.stringify(res.tds));
  console.log('其他换行元素:', JSON.stringify(res.others));
  console.log('表格滚动容器:', JSON.stringify(res.tableScroll));
  await page.screenshot({ path: `wrap-${W}.png` });
  await browser.close();
})();
