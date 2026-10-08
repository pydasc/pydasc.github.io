/* Exercise the built theme and navigation.js in an isolated browser profile. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('playwright');
const root = fs.realpathSync(process.argv[2] || 'site');
const mime = {'.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.json':'application/json', '.svg':'image/svg+xml', '.png':'image/png', '.woff2':'font/woff2'};
const server = http.createServer((req, res) => {
  try {
    let file = path.resolve(root, '.' + decodeURIComponent(new URL(req.url, 'http://localhost').pathname));
    if (fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
    file = fs.realpathSync(file);
    assert(file.startsWith(root + path.sep));
    assert(fs.statSync(file).isFile());
    res.writeHead(200, {'Content-Type': mime[path.extname(file)] || 'application/octet-stream'});
    fs.createReadStream(file).pipe(res);
  } catch {
    res.writeHead(404); res.end('Not found');
  }
});

(async () => {
  let browser;
  try {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const base = `http://127.0.0.1:${server.address().port}`;
    browser = await chromium.launch({headless:true, ...(process.env.DASC_BROWSER_EXECUTABLE ? {executablePath:process.env.DASC_BROWSER_EXECUTABLE} : {})});
    const context = await browser.newContext({viewport:{width:1440,height:900}, reducedMotion:'reduce'});
    await context.route('**/*', route => route.request().url().startsWith(base + '/') ? route.continue() : route.abort());
    const page = await context.newPage();
    page.setDefaultTimeout(5000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => { if (response.url().startsWith(base) && response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    await page.goto(base + '/pydasc/', {waitUntil:'networkidle'});
    const sectionColors = await page.locator('.md-sidebar--primary .md-nav__item--section > .md-nav__link[for]').evaluateAll(elements => elements.filter(el => el.getClientRects().length).map(el => ({text:el.textContent.trim(),foreground:getComputedStyle(el).color,background:getComputedStyle(el.closest('.md-sidebar--primary')).backgroundColor})));
    assert(sectionColors.length > 0, 'desktop must exercise visible project section labels');
    const channels = color => color.match(/[\d.]+/g).map(Number);
    const luminance = rgb => {
      const values = rgb.slice(0,3).map(value => {value /= 255; return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;});
      return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
    };
    for (const colors of sectionColors) {
      const foreground = channels(colors.foreground), background = channels(colors.background);
      const alpha = foreground[3] ?? 1;
      const composite = foreground.slice(0,3).map((value, i) => alpha * value + (1-alpha) * background[i]);
      const a = luminance(composite), b = luminance(background);
      assert((Math.max(a,b)+0.05)/(Math.min(a,b)+0.05) >= 4.5, `low sidebar section contrast: ${colors.text}`);
    }
    assert.equal(await page.locator('.md-footer__link--prev').count(), 0);
    const next = page.locator('.md-footer__link--next');
    assert.equal(new URL(await next.getAttribute('href'), page.url()).pathname, '/pydasc/guides/simulation-workflow/');
    await next.click();
    await page.waitForURL(base + '/pydasc/guides/simulation-workflow/');
    await page.goto(base + '/pydasc/reference/conventions/', {waitUntil:'networkidle'});
    assert.equal(await page.locator('.md-footer__link--next').count(), 0);
    await page.setViewportSize({width:390,height:844});
    await page.goto(base + '/dasc-validation-matrix/', {waitUntil:'networkidle'});
    const control = page.locator('[data-dasc-drawer-control]');
    const drawer = page.locator('#__drawer');
    for (const key of ['Enter','Space']) {
      await control.focus();
      await control.press(key);
      await page.waitForFunction(() => document.querySelector('#__drawer').checked);
      assert.equal(await control.getAttribute('aria-expanded'), 'true');
      assert.equal(await control.getAttribute('aria-label'), 'Close documentation navigation');
      await page.keyboard.press('Escape');
      assert.equal(await drawer.isChecked(), false);
      assert.equal(await control.getAttribute('aria-expanded'), 'false');
      assert.equal(await control.evaluate(el => el === document.activeElement), true);
    }
    const table = page.locator('.dasc-table-scroll').first();
    await table.scrollIntoViewIfNeeded();
    assert(await table.evaluate(el => el.scrollWidth > el.clientWidth), 'mobile table must exercise actual overflow');
    await table.focus();
    await page.keyboard.press('ArrowRight');
    await page.waitForFunction(() => document.querySelector('.dasc-table-scroll').scrollLeft > 0);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'page must not overflow horizontally');
    if (process.env.DASC_BROWSER_REPORT_DIR) {
      const reports = path.resolve(process.env.DASC_BROWSER_REPORT_DIR);
      assert(reports !== root && !reports.startsWith(root + path.sep), 'screenshots must be outside the release artifact');
      fs.mkdirSync(reports, {recursive:true});
      await page.screenshot({path:path.join(reports, 'mobile-table.png')});
      await page.setViewportSize({width:1440,height:900});
      await page.screenshot({path:path.join(reports, 'desktop.png')});
    }
    await page.emulateMedia({media:'print'});
    assert.equal(await page.locator('.md-header').isVisible(), false);
    assert.equal(await table.evaluate(el => getComputedStyle(el).overflow), 'visible');
    assert.equal(await table.locator('table').evaluate(el => getComputedStyle(el).tableLayout), 'fixed');
    assert.deepEqual(errors, []);
    console.log(`Browser checks passed: Chromium ${browser.version()}, Node ${process.version}; desktop/mobile navigation, keyboard focus, scrolling and print CSS.`);
    await context.close();
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
