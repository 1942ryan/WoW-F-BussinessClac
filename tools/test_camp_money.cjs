/**
 * 完整验证：营地徽章 + 金币图标 + 来源悬停浮层
 * 流程：首页 → PVP/联盟 → 使用 → 锻造 → 规划页
 */
const { chromium } = require("playwright");
const path = require("path");

(async () => {
  const root = process.argv[2] || ".";
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
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
  await page.waitForTimeout(1500);

  // 选锻造
  const bs = page.locator("button, a, .prof-card, li");
  const n = await bs.count();
  for (let i = 0; i < n; i++) {
    const t = (await bs.nth(i).innerText()).replace(/\s+/g, " ").trim();
    if (t.startsWith("锻造")) { await bs.nth(i).click(); break; }
  }
  await page.waitForTimeout(2500);
  console.log("URL:", page.url());

  const campCount = await page.locator(".tag.camp").count();
  console.log("营地徽章数量:", campCount);

  if (campCount > 0) {
    const camp = page.locator(".tag.camp").first();
    await camp.scrollIntoViewIfNeeded();
    await camp.hover({ force: true });
    await page.waitForTimeout(700);
    const tip = page.locator(".src-tip");
    console.log("浮层可见:", (await tip.count()) > 0);
    if (await tip.count()) {
      console.log("--- 浮层内容 ---");
      console.log((await tip.innerText()).split("\n").map((s) => "  " + s).join("\n"));
    }
    const b = await camp.boundingBox();
    await page.screenshot({
      path: path.join(root, "camp-hover.png"),
      clip: { x: Math.max(0, b.x - 260), y: Math.max(0, b.y - 80), width: 1000, height: 360 },
    });
  }

  // 金币图标：找一个可见的金额单元格放大
  const money = page.locator(".money-ic:visible").first();
  if (await money.count()) {
    await money.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    const b = await money.boundingBox();
    console.log("money box:", JSON.stringify(b));
    if (b && b.y > 0 && b.y < 1080) {
      await page.screenshot({
        path: path.join(root, "money-zoom.png"),
        clip: { x: Math.max(0, b.x - 12), y: Math.max(0, b.y - 12), width: 240, height: 48 },
      });
    }
  }

  // 计算结果里的收益金额（通常较大，含金币）
  const big = page.locator(".money-ic:visible").last();
  if (await big.count()) {
    await big.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    const b = await big.boundingBox();
    console.log("big money box:", JSON.stringify(b));
    if (b && b.y > 0 && b.y < 1080) {
      await page.screenshot({
        path: path.join(root, "money-big.png"),
        clip: { x: Math.max(0, b.x - 12), y: Math.max(0, b.y - 12), width: 260, height: 48 },
      });
    }
  }

  console.log("控制台错误:", errors.length ? errors.slice(0, 5) : "无");
  await browser.close();
})();
