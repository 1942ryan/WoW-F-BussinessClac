/**
 * 最终验证截图：规划页全貌 + 营地徽章 + 浮层
 */
const { chromium } = require("playwright");
const path = require("path");

(async () => {
  const root = process.argv[2] || ".";
  const w = parseInt(process.argv[3] || "1920", 10);
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: w, height: 1080 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));

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

  await page.screenshot({ path: path.join(root, `final-plan-${w}.png`) });

  // 营地徽章悬停
  const camp = page.locator(".tag.camp").first();
  if (await camp.count()) {
    await camp.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    await camp.hover({ force: true });
    await page.waitForTimeout(700);
    const b = await camp.boundingBox();
    await page.screenshot({
      path: path.join(root, `final-camp-${w}.png`),
      clip: { x: Math.max(0, b.x - 300), y: Math.max(0, b.y - 40), width: 1000, height: 340 },
    });
    console.log("徽章数:", await page.locator(".tag.camp").count());
  }

  console.log("控制台错误:", errors.length ? errors.slice(0, 5) : "无");
  await browser.close();
})();
