// Run inside the existing minlag/mermaid-cli Docker image.
const fs = require('fs');
const puppeteer = require('/home/mermaidcli/node_modules/puppeteer');

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: '/usr/bin/chromium',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  try {
    const page = await browser.newPage();
    await page.setContent('<style>html,body{margin:0;background:transparent}</style>'
      + fs.readFileSync(process.argv[2], 'utf8'));
    await page.evaluate(() => document.fonts.ready);
    const svg = await page.$('svg');
    const bounds = await svg.boundingBox();
    await page.setViewport({
      width: Math.ceil(bounds.width), height: Math.ceil(bounds.height), deviceScaleFactor: 1,
    });
    await svg.screenshot({path: process.argv[3], omitBackground: true});
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
