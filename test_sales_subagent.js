const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({
    headless: "new",
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  
  // Login first
  await page.goto('http://127.0.0.1:5000/login');
  await page.type('#username', 'admin');
  await page.type('#password', 'admin');
  await page.click('button[type="submit"]');
  await page.waitForNavigation();
  
  // Go to Sales page
  await page.goto('http://127.0.0.1:5000/sales');
  
  // Find the first product search input
  await page.waitForSelector('.product-search-input');
  
  // Type 'AFGHAN ALMOND NO SHELL'
  await page.type('.product-search-input', 'AFGHAN ALMOND NO SHELL');
  
  // Wait for suggestion to appear
  await page.waitForSelector('.suggestion-item');
  
  // Click the suggestion
  await page.click('.suggestion-item');
  
  // Wait a bit to see if variants appear
  await new Promise(r => setTimeout(r, 500));
  
  // Check if variants are visible
  const isVisible = await page.evaluate(() => {
    const suggestions = document.querySelector('.product-suggestions');
    return suggestions && suggestions.style.display !== 'none' && suggestions.innerHTML.includes('100g');
  });
  
  console.log("Variants visible:", isVisible);
  
  if (!isVisible) {
      console.log("productSuggestions display:", await page.evaluate(() => document.querySelector('.product-suggestions').style.display));
      console.log("productSuggestions HTML:", await page.evaluate(() => document.querySelector('.product-suggestions').innerHTML));
      console.log("productSuggestions rect:", await page.evaluate(() => JSON.stringify(document.querySelector('.product-suggestions').getBoundingClientRect())));
  }

  await browser.close();
})();
