const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: "new" });
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  
  await page.goto('file:///home/aseda/Desktop/english_tech/test_flutter_cors.html');
  await page.click('button');
  await page.waitForTimeout(1000);
  let content = await page.$eval('#result', el => el.innerText);
  console.log('HTTP CORS result:');
  console.log(content);
  
  await page.goto('file:///home/aseda/Desktop/english_tech/test_flutter_ws_cors.html');
  await page.click('button');
  await page.waitForTimeout(1000);
  content = await page.$eval('#result', el => el.innerText);
  console.log('WS CORS result:');
  console.log(content);
  
  await browser.close();
})();
