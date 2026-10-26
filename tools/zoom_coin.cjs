const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 900, height: 300 }, deviceScaleFactor: 4 });
  await page.setContent(`<div style="padding:20px;background:#f7f4ec;font:13px/1 sans-serif">
    <span id="a" style="font-size:15px">1<svg width="13" height="13" viewBox="0 0 16 16" style="vertical-align:-2px"><defs><radialGradient id="g" cx="36%" cy="28%" r="80%"><stop offset="0%" stop-color="#fdf3ad"/><stop offset="48%" stop-color="#d8c14d"/><stop offset="100%" stop-color="#8a6a13"/></radialGradient></defs><circle cx="8" cy="8" r="7.1" fill="#6a4f0f"/><circle cx="8" cy="8" r="6.05" fill="url(#g)"/><ellipse cx="6.1" cy="5.05" rx="1.95" ry="1.1" fill="#fff" opacity="0.45" transform="rotate(-28 6.1 5.05)"/></svg></span>
    <span style="font-size:15px">87<svg width="13" height="13" viewBox="0 0 16 16" style="vertical-align:-2px"><defs><radialGradient id="h" cx="36%" cy="28%" r="80%"><stop offset="0%" stop-color="#f4f3f5"/><stop offset="48%" stop-color="#adacb0"/><stop offset="100%" stop-color="#67666b"/></radialGradient></defs><circle cx="8" cy="8" r="7.1" fill="#46454a"/><circle cx="8" cy="8" r="6.05" fill="url(#h)"/><ellipse cx="6.1" cy="5.05" rx="1.95" ry="1.1" fill="#fff" opacity="0.45" transform="rotate(-28 6.1 5.05)"/></svg></span>
    <span style="font-size:15px">58<svg width="13" height="13" viewBox="0 0 16 16" style="vertical-align:-2px"><defs><radialGradient id="i" cx="36%" cy="28%" r="80%"><stop offset="0%" stop-color="#eab48a"/><stop offset="48%" stop-color="#ac714c"/><stop offset="100%" stop-color="#6b3819"/></radialGradient></defs><circle cx="8" cy="8" r="7.1" fill="#572c14"/><circle cx="8" cy="8" r="6.05" fill="url(#i)"/><ellipse cx="6.1" cy="5.05" rx="1.95" ry="1.1" fill="#fff" opacity="0.45" transform="rotate(-28 6.1 5.05)"/></svg></span>
  </div>`);
  await page.screenshot({ path: 'coin-zoom.png', clip: { x: 10, y: 10, width: 200, height: 50 } });
  await browser.close();
})();
