/**
 * 走完整流程：首页 → 选服务器/阵营 → 进入 → 选专业 → 规划页 → 检查营地徽章 + 金币图标
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
  await page.waitForTimeout(400);
  await page.locator("button", { hasText: /^(使用|创建) PVP·联盟$/ }).first().click();
  await page.waitForTimeout(1800);
  console.log("URL:", page.url());
  console.log("可见文本:", (await page.locator("body").innerText()).replace(/\s+/g, " ").slice(0, 600));

  await browser.close();
})();
