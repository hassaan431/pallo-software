const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  // Mobile
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('http://localhost:3000');
  await page.screenshot({ path: '/Users/hassaanjazz/.gemini/antigravity-ide/brain/32313f4e-5957-4569-b428-25fb5efec103/mobile_screenshot.png', fullPage: true });

  await browser.close();
})();
