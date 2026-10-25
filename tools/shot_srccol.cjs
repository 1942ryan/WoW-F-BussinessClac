/**
 * 截「来源」列（td:nth-child(6)）看徽章是否换行/溢出
 */
const { chromium } = require("playwright");
const path = require("path");

(async () => {
  const root = process.argv[2] || ".";
  const w = parseInt(process.argv[3] || "1920", 10);
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: w, height: 1080 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();

  await page.goto("http://127.0.0.1:8787/", { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await page.getByRole("button", { name: "PVP", exact: true }).first().click();
  await page.waitForTimeout(300);
  await page.locator("button.faction", { hasText: "联盟" }).first().click();
  await page.waitForTimeout(300);
  await page.locator("button", { hasText: /^(使用|创建) PVP·联盟$/ }).first().click();
  await page.waitForTimeout(1400);
  const bs = page.locator("button, a, .prof-card, li");
  const n = await bs.count();
  for (let i = 0; i < n; i++) {
    const t = (await bs.nth(i).innerText()).replace(/\s+/g, " ").trim();
    if (t.startsWith("锻造")) { await bs.nth(i).click(); break; }
  }
  await page.waitForTimeout(2500);

  // 找第一个带营地徽章的行，量它的来源格
  const info = await page.evaluate(() => {
    const camp = document.querySelector(".tag.camp");
    if (!camp) return null;
    const tr = camp.closest("tr");
    const td = camp.closest("td");
    const r = td.getBoundingClientRect();
    // 来源格内所有元素
    const kids = [...td.querySelectorAll(".src-cell > *")].map((e) => {
      const b = e.getBoundingClientRect();
      return { cls: e.className, text: e.textContent.trim(), w: Math.round(b.width), h: Math.round(b.height), top: Math.round(b.top) };
    });
    return {
      tdW: Math.round(r.width), tdH: Math.round(r.height),
      kids,
      sameLine: new Set(kids.map((k) => k.top)).size === 1,
    };
  });
  console.log(w + "px →", JSON.stringify(info, null, 1));

  // 截该行
  const camp = page.locator(".tag.camp").first();
  await camp.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  const b = await camp.boundingBox();
  await page.screenshot({
    path: path.join(root, `src-col-${w}.png`),
    clip: { x: Math.max(0, b.x - 260), y: Math.max(0, b.y - 30), width: 420, height: 90 },
  });
  await browser.close();
})();
