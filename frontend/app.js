const $ = (selector) => document.querySelector(selector);
let products = [];
let selectedProduct = null;
let quoteVersion = 0;
let currentQuote = null;
let submitting = false;
let adding = false;
let loadingProducts = false;
let orderLocked = false;
let catalogError = '';

// Presentation only: the Product API remains the source of names and prices.
function presentation(product) {
  const name = product.name.toLowerCase();
  if (/notebook|sketchbook|journal|notepad/.test(name)) return {
    category: 'Notebooks', image: 'notebook', background: '#f0e5d6',
    description: /sketch/.test(name) ? 'A space for sketches, quick studies, and your next idea.' : 'Keep lecture notes, to-do lists, and everyday ideas together.',
  };
  if (/\b(pens?|markers?|highlighters?)\b/.test(name)) return {
    category: 'Stationery', image: 'pens', background: '#e8e9dc',
    description: 'For taking notes, marking key ideas, and putting plans on paper.',
  };
  if (/pencil|stationery/.test(name)) return {
    category: 'Stationery', image: 'stationery', background: '#eee8d6',
    description: 'An everyday companion for notes, problem-solving, and sketching.',
  };
  if (/folder|binder/.test(name)) return {
    category: 'Campus essentials', image: 'notebook', background: '#f0e5d6',
    description: 'Bring a little order to your coursework and study routine.',
  };
  return {
    category: 'Books & learning', image: 'book', background: '#e3eadf',
    description: /biology/.test(name) ? 'Make room on your reading list for a closer look at the living world.'
      : /study/.test(name) ? 'Build your reading list around a more thoughtful study routine.'
      : 'A new addition to your campus reading list. Explore at your own pace.',
  };
}

function money(amount) {
  const [whole, fraction = ''] = String(amount).split('.');
  return `$${BigInt(whole).toLocaleString('en-CA')}.${fraction.padEnd(2, '0')} CAD`;
}

async function api(path, payload) {
  let response;
  try {
    response = await fetch(`/api${path}`, {
      ...(payload === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
      signal: AbortSignal.timeout(20000),
    });
  } catch {
    const error = new Error(payload && path === '/orders'
      ? 'The order response was interrupted. It may have been saved. Avoid placing it again until you have checked your receipt.'
      : 'The bookstore could not be reached. Check your connection and try again.');
    error.uncertain = path === '/orders' && payload !== undefined;
    throw error;
  }
  const data = await response.json().catch(() => null);
  if (!response.ok || !data) {
    const error = new Error(data?.error || 'The bookstore service is unavailable. Please try again shortly.');
    error.uncertain = path === '/orders' && payload !== undefined && (response.status >= 500 || response.ok);
    throw error;
  }
  return data;
}

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function toast(message) {
  $('#toast').textContent = message;
  $('#toast').hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { $('#toast').hidden = true; }, 5000);
}

function renderProducts() {
  const term = $('#search').value.trim().toLowerCase();
  const visible = products.filter((p) => p.name.toLowerCase().includes(term));
  $('#products').replaceChildren();
  $('#product-count').textContent = `${visible.length} ${visible.length === 1 ? 'product' : 'products'}`;
  $('#catalog-status').textContent = catalogError || (!visible.length
    ? (products.length ? 'No matches. Try another title or clear your search.' : 'The collection is empty. Visit Manage products to add your first item.') : '');
  for (const product of visible) {
    const info = presentation(product);
    const card = node('article', 'product-card');
    const image = node('img', 'product-art');
    image.src = `/assets/${info.image}.svg`;
    image.alt = `Representative ${info.category.toLowerCase()} illustration`;
    image.width = 480;
    image.height = 360;
    image.style.setProperty('--tile', info.background);
    const bottom = node('div', 'product-bottom');
    const button = node('button', 'shop-button', 'Choose & order');
    button.setAttribute('aria-label', `Order ${product.name}`);
    button.addEventListener('click', () => openOrder(product));
    bottom.append(node('span', 'price', money(product.price_cad)), button);
    card.append(image, node('p', 'product-category', info.category), node('h3', '', product.name), node('p', 'product-description', info.description), bottom);
    $('#products').append(card);
  }
  $('#manage-list').replaceChildren();
  $('#manage-status').textContent = catalogError || (products.length ? `${products.length} products saved` : 'No products yet. Add the first one here.');
  for (const product of products) {
    const row = node('li');
    row.append(node('span', '', product.name), node('span', '', money(product.price_cad)));
    $('#manage-list').append(row);
  }
}

async function loadProducts() {
  if (loadingProducts) return;
  loadingProducts = true;
  $('#refresh').disabled = true;
  $('#products').setAttribute('aria-busy', 'true');
  $('#catalog-status').textContent = 'Loading the collection…';
  $('#manage-status').textContent = 'Loading saved products…';
  try {
    const catalog = await api('/products');
    if (!Array.isArray(catalog.products) || !catalog.products.every((product) =>
      product && Number.isSafeInteger(product.id) && product.id > 0 && typeof product.name === 'string'
      && product.currency === 'CAD' && typeof product.price_cad === 'string' && /^[0-9]+\.[0-9]{2}$/.test(product.price_cad))) {
      throw new Error('The bookstore returned an invalid collection. Please try again.');
    }
    products = catalog.products;
    catalogError = '';
    renderProducts();
  } catch (error) {
    catalogError = `${error.message} Use Refresh collection in the shop to retry.`;
    renderProducts();
  } finally {
    loadingProducts = false;
    $('#refresh').disabled = false;
    $('#products').setAttribute('aria-busy', 'false');
  }
}

function route() {
  const managing = location.hash === '#manage';
  document.querySelectorAll('[data-shop]').forEach((element) => { element.hidden = managing; });
  $('#manage').hidden = !managing;
  $('#shop-nav').toggleAttribute('aria-current', !managing);
  $('#manage-nav').toggleAttribute('aria-current', managing);
  (managing ? $('#manage-nav') : $('#shop-nav')).setAttribute('aria-current', 'page');
}

function openDialog(selector) {
  const dialog = $(selector);
  dialog.querySelectorAll('.form-error').forEach((element) => { element.textContent = ''; });
  dialog.showModal();
}

function openOrder(product) {
  selectedProduct = product;
  orderLocked = false;
  const info = presentation(product);
  $('#order-name').textContent = product.name;
  $('#order-description').textContent = info.description;
  $('#order-image').src = `/assets/${info.image}.svg`;
  $('#quantity').value = '1';
  $('#quantity').disabled = false;
  $('#place-order').textContent = 'Place order';
  openDialog('#order-dialog');
  updateQuote();
}

async function updateQuote() {
  const version = ++quoteVersion;
  currentQuote = null;
  $('#place-order').disabled = true;
  $('#quote-total').textContent = '—';
  $('#unit-price').textContent = '—';
  $('#order-form .form-error').textContent = '';
  if (!$('#quantity').checkValidity()) {
    $('#quote-status').textContent = 'Enter a whole-number quantity from 1 to 2,147,483,647.';
    return;
  }
  $('#quote-status').textContent = 'Calculating your total…';
  const quantity = Number($('#quantity').value);
  const productId = selectedProduct.id;
  try {
    const quote = await api(`/quotes/${productId}?quantity=${quantity}`);
    if (version !== quoteVersion) return;
    currentQuote = { ...quote, quantity, productId };
    $('#quote-total').textContent = money(quote.total_cad);
    $('#unit-price').textContent = money(quote.unit_price_cad);
    $('#quote-status').textContent = 'Total confirmed by the bookstore.';
    $('#place-order').disabled = submitting || orderLocked;
  } catch (error) {
    if (version === quoteVersion) {
      $('#quote-status').textContent = '';
      $('#order-form .form-error').textContent = `${error.message} Change the quantity or reopen this product to retry.`;
    }
  }
}

function rememberOrder(id) {
  try { localStorage.setItem('campus-last-order', String(id)); } catch { /* Optional browser convenience. */ }
}

function renderReceipt(receipt, justPlaced = false) {
  const container = node('section', 'receipt');
  container.append(node('h3', '', justPlaced ? 'Your order is saved.' : 'Your saved receipt.'));
  const details = node('dl');
  for (const [label, value] of [
    ['Order number', `#${receipt.order_id}`], ['Product', receipt.name],
    ['Quantity', receipt.quantity], ['Unit price', money(receipt.unit_price_cad)],
    ['Total · CAD', money(receipt.total_cad)],
  ]) {
    const row = node('div', label.startsWith('Total') ? 'receipt-total' : '');
    row.append(node('dt', '', label), node('dd', '', value));
    details.append(row);
  }
  container.append(details, node('p', 'muted', 'Retrieved from your saved order. Keep the order number for your records.'));
  const actions = node('div', 'receipt-actions');
  const copy = node('button', 'button light', 'Copy order number');
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(String(receipt.order_id));
      toast('Order number copied.');
    } catch {
      toast(`Copy is unavailable. Your order number is ${receipt.order_id}.`);
    }
  });
  const print = node('button', 'button light', 'Print receipt');
  print.addEventListener('click', () => window.print());
  const keepShopping = node('button', 'button dark full', 'Continue shopping');
  keepShopping.addEventListener('click', () => {
    $('#receipt-dialog').close();
    location.hash = '#catalog';
    $('#catalog').scrollIntoView();
  });
  actions.append(copy, print, keepShopping);
  $('#receipt-result').replaceChildren(container, actions);
  $('#receipt-title').textContent = justPlaced ? 'One for the books.' : 'Your receipt.';
  $('#lookup-form').hidden = true;
  $('#lookup-form [name=order]').value = String(receipt.order_id);
  rememberOrder(receipt.order_id);
}

function openLookup() {
  $('#receipt-title').textContent = 'Find your receipt.';
  $('#receipt-result').replaceChildren();
  $('#lookup-form').hidden = false;
  $('#lookup-status').textContent = '';
  try { $('#lookup-form [name=order]').value = localStorage.getItem('campus-last-order') || ''; } catch { /* Optional convenience. */ }
  openDialog('#receipt-dialog');
}

$('#search').addEventListener('input', () => { if (!loadingProducts) renderProducts(); });
$('#refresh').addEventListener('click', loadProducts);
$('#lookup-open').addEventListener('click', openLookup);
$('#lookup-banner').addEventListener('click', openLookup);
window.addEventListener('hashchange', route);
document.querySelectorAll('[data-close]').forEach((button) => button.addEventListener('click', () => button.closest('dialog').close()));
$('#quantity').addEventListener('input', updateQuote);
$('#order-dialog').addEventListener('cancel', (event) => { if (submitting) event.preventDefault(); });
$('#order-dialog').addEventListener('close', () => { quoteVersion++; });

$('#add-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (adding) return;
  const form = event.currentTarget;
  const button = form.querySelector('[type=submit]');
  const name = form.elements.name.value.trim();
  form.querySelector('.form-error').textContent = '';
  $('#add-status').textContent = '';
  if (!name) { form.querySelector('.form-error').textContent = 'Enter a product name, not just spaces.'; return; }
  adding = true;
  button.disabled = true;
  button.textContent = 'Saving product…';
  try {
    const product = await api('/products', { name, price_cad: form.elements.price.value, currency: 'CAD' });
    form.reset();
    $('#search').value = '';
    $('#add-status').textContent = `${product.name} is saved and available in the shop.`;
    toast('Product added to the collection.');
    await loadProducts();
  } catch (error) { form.querySelector('.form-error').textContent = error.message; }
  finally { adding = false; button.disabled = false; button.textContent = 'Save product'; }
});

$('#order-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (submitting || orderLocked || !currentQuote || currentQuote.productId !== selectedProduct.id || currentQuote.quantity !== Number($('#quantity').value)) return;
  submitting = true;
  const button = $('#place-order');
  button.disabled = true;
  button.textContent = 'Saving your order…';
  $('#quantity').disabled = true;
  $('#order-dialog .close').disabled = true;
  $('#order-form .form-error').textContent = '';
  let savedId;
  try {
    const order = await api('/orders', { product_id: selectedProduct.id, quantity: currentQuote.quantity });
    savedId = order.order_id;
    orderLocked = true;
    rememberOrder(savedId);
    $('#quote-status').textContent = `Order #${savedId} saved. Retrieving your receipt…`;
    const receipt = await api(`/orders/${savedId}`);
    $('#order-dialog').close();
    openDialog('#receipt-dialog');
    renderReceipt(receipt, true);
  } catch (error) {
    orderLocked = orderLocked || Boolean(error.uncertain);
    $('#order-form .form-error').textContent = savedId
      ? `Order #${savedId} was saved, but its receipt could not be loaded. Close this window and use Find receipt with order number ${savedId}.`
      : error.message;
  } finally {
    submitting = false;
    button.disabled = orderLocked || !currentQuote;
    button.textContent = orderLocked ? 'Order submitted — check receipt' : 'Place order';
    $('#quantity').disabled = orderLocked;
    $('#order-dialog .close').disabled = false;
  }
});

$('#lookup-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button');
  if (button.disabled) return;
  button.disabled = true;
  form.querySelector('.form-error').textContent = '';
  $('#lookup-status').textContent = 'Retrieving your saved receipt…';
  $('#receipt-result').replaceChildren();
  try {
    const id = form.elements.order.value;
    if (BigInt(id) > 9223372036854775807n) throw new Error('Enter a valid order number.');
    renderReceipt(await api(`/orders/${id}`));
  } catch (error) { form.querySelector('.form-error').textContent = error.message; }
  finally { button.disabled = false; $('#lookup-status').textContent = ''; }
});

route();
loadProducts();
