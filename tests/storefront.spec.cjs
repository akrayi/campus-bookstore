// Test-only browser tooling: see README.md. Never writes to the demo stack.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const base = process.env.STOREFRONT_URL || 'http://127.0.0.1:3100';
const target = new URL(base);
if (!['localhost', '127.0.0.1'].includes(target.hostname) || target.port !== '3100') {
  throw new Error('Browser tests must target the isolated test stack on localhost:3100.');
}
const composeArgs = ['compose', '-p', 'campus-bookstore-tests', '-f', 'compose.yaml', '-f', 'compose.test.yaml'];
const compose = (...args) => execFileSync('docker', [...composeArgs, ...args], { cwd: path.resolve(__dirname, '..'), encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
const screenshotDir = process.env.TEMP || '/tmp';

(async () => {
  const browser = await chromium.launch({ headless: true });
  let serviceStopped = false;
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, permissions: ['clipboard-read', 'clipboard-write'] });
    const page = await context.newPage();
    const errors = [];
    let expectedFailure = false;
    let productPosts = 0;
    let orderPosts = 0;
    let receiptGets = 0;
    page.on('pageerror', (e) => errors.push(e.message));
    page.on('console', (message) => { if (message.type() === 'error' && !expectedFailure) errors.push(message.text()); });
    page.on('request', (request) => {
      if (request.url().endsWith('/api/products') && request.method() === 'POST') productPosts++;
      if (request.url().endsWith('/api/orders') && request.method() === 'POST') orderPosts++;
      if (/\/api\/orders\/\d+$/.test(request.url()) && request.method() === 'GET') receiptGets++;
    });
    await page.goto(base);
    await page.waitForFunction(() => document.querySelector('#products').getAttribute('aria-busy') === 'false');
    await page.getByRole('link', { name: 'Manage products', exact: true }).click();
    await page.getByText('DEMO MANAGEMENT AREA', { exact: true }).waitFor();
    await page.getByLabel('Product name', { exact: true }).fill('   ');
    await page.getByLabel('Price in CAD', { exact: true }).fill('4.50');
    await page.getByRole('button', { name: 'Save product', exact: true }).click();
    await page.getByText('Enter a product name, not just spaces.', { exact: true }).waitFor();
    const name = `Browser Notebook ${Date.now()}`;
    await page.getByLabel('Product name', { exact: true }).fill(name);
    await page.getByLabel('Price in CAD', { exact: true }).fill('-1');
    assert.equal(await page.locator('#add-form').evaluate((form) => form.checkValidity()), false);
    await page.getByLabel('Price in CAD', { exact: true }).fill('4.50');
    await page.locator('#add-form').evaluate((form) => { form.requestSubmit(); form.requestSubmit(); });
    await page.getByText(`${name} is saved and available in the shop.`, { exact: true }).waitFor();
    assert.equal(productPosts, 1, 'Repeated product submission is blocked');
    await page.getByRole('link', { name: 'Shop', exact: true }).click();
    await page.getByRole('button', { name: `Order ${name}`, exact: true }).waitFor();
    await page.getByRole('searchbox').fill('no-match-xyz');
    await page.getByText('No matches. Try another title or clear your search.', { exact: true }).waitFor();
    await page.getByRole('searchbox').fill(name);
    assert.equal(await page.locator('.product-card').count(), 1);
    await page.getByRole('button', { name: `Order ${name}`, exact: true }).click();
    await page.getByLabel('Quantity', { exact: true }).fill('0');
    assert.equal(await page.getByRole('button', { name: 'Place order', exact: true }).isDisabled(), true);
    await page.getByLabel('Quantity', { exact: true }).fill('2');
    await page.waitForFunction(() => document.querySelector('#quote-total').textContent === '$9.00 CAD');
    assert.equal(await page.locator('#unit-price').innerText(), '$4.50 CAD');
    await page.locator('#order-form').evaluate((form) => { form.requestSubmit(); form.requestSubmit(); });
    await page.getByText('Your order is saved.', { exact: true }).waitFor();
    assert.equal(orderPosts, 1, 'Repeated checkout creates one order');
    assert.equal(receiptGets, 1, 'Success displays a receipt retrieved through GET');
    const id = await page.locator('#lookup-form [name=order]').inputValue();
    assert.match(await page.locator('#receipt-result').innerText(), /\$9\.00 CAD/);
    const saved = await (await page.request.get(`${base}/api/orders/${id}`)).json();
    assert.equal(saved.quantity, 2);
    assert.equal(saved.total_cad, '9.00');
    assert.equal(saved.name, name);
    const row = compose('exec', '-T', 'orders-db', 'psql', '-U', 'bookstore', '-d', 'bookstore_orders', '-At', '-F', '|', '-c', `SELECT product_name, quantity, unit_price_cents, currency FROM orders WHERE id = ${Number(id)}`);
    assert.equal(row.trim(), `${name}|2|450|CAD`);
    await page.getByRole('button', { name: 'Copy order number', exact: true }).click();
    await page.getByText('Order number copied.', { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), id);
    await page.evaluate(() => { window.printCalls = 0; window.print = () => { window.printCalls++; }; });
    await page.getByRole('button', { name: 'Print receipt', exact: true }).click();
    assert.equal(await page.evaluate(() => window.printCalls), 1);
    await page.emulateMedia({ media: 'print' });
    assert.equal(await page.locator('#catalog').isVisible(), false);
    assert.equal(await page.locator('.receipt').isVisible(), true);
    await page.pdf({ path: path.join(screenshotDir, 'campus-receipt.pdf'), format: 'A4' });
    await page.emulateMedia({ media: 'screen' });
    await page.getByRole('button', { name: 'Continue shopping', exact: true }).click();
    await page.reload();
    await page.getByRole('button', { name: 'Find receipt', exact: true }).click();
    assert.equal(await page.getByLabel('Order number', { exact: true }).inputValue(), id);
    await page.getByRole('button', { name: 'Look up receipt', exact: true }).click();
    await page.getByText('Your saved receipt.', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Close receipt', exact: true }).click();
    await page.getByRole('button', { name: 'Find receipt', exact: true }).click();
    await page.getByLabel('Order number', { exact: true }).fill('9223372036854775807');
    expectedFailure = true;
    await page.getByRole('button', { name: 'Look up receipt', exact: true }).click();
    await page.getByText('Order not found.', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Close receipt', exact: true }).click();
    expectedFailure = false;

    // Real backend outage, restricted to the test Compose project; always restore it.
    expectedFailure = true;
    compose('stop', 'order-service');
    serviceStopped = true;
    await page.getByRole('button', { name: `Order ${name}`, exact: true }).click();
    await page.getByText(/The bookstore service is unavailable/).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Place order', exact: true }).isDisabled(), true);
    await page.getByRole('button', { name: 'Close order', exact: true }).click();
    compose('up', '-d', '--no-deps', '--force-recreate', '--wait', 'order-service');
    serviceStopped = false;
    await page.getByRole('button', { name: `Order ${name}`, exact: true }).click();
    await page.waitForFunction(() => document.querySelector('#quote-total').textContent === '$4.50 CAD');
    await page.getByRole('button', { name: 'Close order', exact: true }).click();
    expectedFailure = false;

    // A saved order must never be submitted again when only its receipt GET fails.
    await page.route('**/api/orders/*', (route) => route.fulfill({ status: 503, json: { error: 'Receipt temporarily unavailable.' } }));
    expectedFailure = true;
    await page.getByRole('button', { name: `Order ${name}`, exact: true }).click();
    await page.waitForFunction(() => !document.querySelector('#place-order').disabled);
    await page.getByRole('button', { name: 'Place order', exact: true }).click();
    await page.locator('#order-form .form-error').filter({ hasText: 'was saved, but its receipt could not be loaded' }).waitFor();
    assert.equal(await page.locator('#place-order').isDisabled(), true);
    assert.equal(orderPosts, 2, 'Receipt failure does not resubmit a saved order');
    await page.getByRole('button', { name: 'Close order', exact: true }).click();
    await page.unroute('**/api/orders/*');
    expectedFailure = false;
    await page.getByRole('button', { name: 'Find receipt', exact: true }).click();
    await page.getByRole('button', { name: 'Look up receipt', exact: true }).click();
    await page.getByText('Your saved receipt.', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Continue shopping', exact: true }).click();

    await page.getByRole('searchbox').fill('');
    await page.evaluate(() => { document.activeElement.blur(); window.scrollTo(0, 0); });
    await page.screenshot({ path: path.join(screenshotDir, 'campus-desktop.png'), fullPage: true });
    for (const width of [320, 390, 768]) {
      await page.setViewportSize({ width, height: 900 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `No overflow at ${width}px`);
      const size = await page.locator('.product-art').first().boundingBox();
      assert.ok(Math.abs(size.height / size.width - 0.75) < 0.02, 'Consistent 4:3 product images');
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
    await page.screenshot({ path: path.join(screenshotDir, 'campus-mobile.png'), fullPage: true });
    await page.getByRole('button', { name: `Order ${name}`, exact: true }).click();
    await page.waitForFunction(() => document.querySelector('#quote-total').textContent === '$4.50 CAD');
    assert.equal(await page.locator('#order-dialog').evaluate((e) => e.getBoundingClientRect().width < innerWidth), true);
    await page.screenshot({ path: path.join(screenshotDir, 'campus-checkout-mobile.png') });
    await page.getByRole('button', { name: 'Close order', exact: true }).click();

    expectedFailure = true;
    await page.route('**/api/products', (route) => route.fulfill({ status: 503, json: { error: 'Catalog temporarily unavailable.' } }));
    await page.getByRole('button', { name: 'Refresh collection', exact: true }).click();
    await page.locator('#catalog-status').filter({ hasText: 'Catalog temporarily unavailable.' }).waitFor();
    await page.getByRole('searchbox').fill('notebook');
    assert.match(await page.locator('#catalog-status').innerText(), /Catalog temporarily unavailable/);
    await page.unroute('**/api/products');
    expectedFailure = false;
    await page.route('**/api/products', (route) => route.fulfill({ json: { products: null } }));
    await page.getByRole('button', { name: 'Refresh collection', exact: true }).click();
    await page.locator('#catalog-status').filter({ hasText: 'invalid collection' }).waitFor();
    await page.unroute('**/api/products');
    await page.route('**/api/products', (route) => route.fulfill({ json: { products: [{ id: 123, name: 'Independent Study', currency: 'CAD', price_cad: '4.50' }] } }));
    await page.getByRole('searchbox').fill('');
    await page.getByRole('button', { name: 'Refresh collection', exact: true }).click();
    await page.getByRole('heading', { name: 'Independent Study', exact: true }).waitFor();
    assert.match(await page.locator('.product-art').getAttribute('src'), /book\.svg$/);
    await page.unroute('**/api/products');

    // Empty-catalog UI state; only this state uses a controlled response.
    await page.route('**/api/products', (route) => route.fulfill({ json: { products: [] } }));
    await page.getByRole('button', { name: 'Refresh collection', exact: true }).click();
    await page.getByText('The collection is empty. Visit Manage products to add your first item.', { exact: true }).waitFor();
    await page.unroute('**/api/products');
    await page.getByRole('button', { name: 'Refresh collection', exact: true }).click();
    await page.locator('.product-card').first().waitFor();
    assert.deepEqual(errors, [], 'No unexpected browser console or script errors');
    console.log(JSON.stringify({ status: 'passed', order_id: id, product: name, postgres: 'matched', repeated_clicks: 'blocked', backend_outage: 'reported', receipt: 'retrieved, copied, print checked', widths: [320, 390, 768, 1440] }));
  } finally {
    if (serviceStopped) compose('start', '--wait', 'order-service');
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
