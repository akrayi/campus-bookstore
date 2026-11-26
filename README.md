# Campus Bookstore

For the final assessed demo, run the **complete Kubernetes application** using
[the CMD startup and shutdown guide](docs/DEMO-CMD.md). The monitored website is
on **http://localhost:3002**; the independent Compose demo stays on port 3000.
See [architecture and request-flow diagrams](docs/ARCHITECTURE.md),
[CI/CD setup](docs/CICD.md).

```cmd
python scripts/init_env.py
python scripts/setup_cluster.py
python scripts/deploy.py
python scripts/setup_monitoring.py
python scripts/verify_cluster.py
scripts\start_demo.cmd
```

Run these from the repository root after Docker Desktop Kubernetes is ready.
The setup preserves existing database credentials and volumes. The deployment
builds and validates all application components before waiting for readiness.
The API gateway runs without root and limits API traffic. Both APIs use Gunicorn,
database readiness checks and Prometheus HTTP metrics. Compose services now use
`restart: unless-stopped` and can restart with Docker Desktop unless manually stopped.

A green-and-cream storefront for the existing Flask Product and Order APIs. DM Sans controls and Instrument Serif headings are self-hosted with their OFL licenses. Local SVG illustrations cover books, notebooks, pens, and pencils.

## Run the demo

Start Docker Desktop and keep your existing `POSTGRES_PASSWORD` in the ignored `.env` file. Use the password already associated with the database volume.

```powershell
docker compose up --build -d --wait
```

Open **http://localhost:3000**. Navigation provides **Shop**, **Find receipt**, and **Manage products**. Management is explicitly an unauthenticated demo area. Products can be added there; editing and deletion are not offered by the existing API.

Checkout preserves the single-product order model. Choose a quantity, review the server-calculated unit price and total in CAD, and place one order. The success screen retrieves the persisted receipt using `GET /orders/{id}` and offers **Copy order number**, **Print receipt**, and **Continue shopping**. A browser can remember the last order number. No payment is collected and no tax or shipping is added.

## Add realistic demo products

Run this explicit command after the demo services are healthy:

```powershell
python scripts/seed_demo.py
```

The script uses only the Product API. It adds six example books, notebooks, and stationery products. Sequential reruns skip existing names (case-insensitive), preserving their current prices and all other data. It never deletes or updates existing records. Run one seed process at a time: the existing API has no unique SKU or idempotency key. `DEMO_PRODUCT_URL` optionally selects a different Product API.

Existing test-looking entries from earlier runs are retained to preserve local data. New automated tests never target the demo catalog. Names and prices come from the API; categories and brief descriptions are presentation hints inferred from names. Images are representative category illustrations, not product photographs. The API contract and schemas are unchanged by this update.

## Test without changing demo data

Tests use a dedicated Compose project, network, ports, and named volumes. The override also uses distinct volume keys and a default test project name. Python and browser tests refuse the demo ports.

```powershell
docker compose -p campus-bookstore-tests -f compose.yaml -f compose.test.yaml up --build -d --wait

docker compose -p campus-bookstore-tests -f compose.yaml -f compose.test.yaml cp product-service/test_app.py product-service:/app/test_app.py
docker compose -p campus-bookstore-tests -f compose.yaml -f compose.test.yaml cp order-service/test_orders.py order-service:/app/test_orders.py
docker compose -p campus-bookstore-tests -f compose.yaml -f compose.test.yaml exec -T product-service python -m unittest test_app -v
docker compose -p campus-bookstore-tests -f compose.yaml -f compose.test.yaml exec -T order-service python -m unittest test_orders -v
python -m unittest discover -s tests -p "test_*.py" -v
```

Run from the repository root. Unit tests use a temporary SQLite database and mocks. Integration tests use real test services and PostgreSQL; the storefront test also checks the saved row with `psql` inside the test database container. They cover product creation/retrieval, catalog listing, quotes, saved receipts, unknown products, and invalid quantities. CI uses the same test override.

For browser and offline Kubernetes manifest checks, install the locked test dependencies (ignored `tests/node_modules`):

```powershell
npm.cmd ci --prefix tests
npm.cmd exec --prefix tests -- playwright install chromium
npm.cmd run --prefix tests manifests
npm.cmd run --prefix tests browser
```

Run the browser checks after Python tests, not concurrently. They stop and restore only the test Order service to verify real backend-failure feedback. They check repeated-click protection, quantity and CAD totals, persisted receipt retrieval, PostgreSQL contents, copy/print/continue actions, empty results, invalid input, browser errors, and widths of 320, 390, 768, and 1440 pixels. Empty/malformed catalog states and a failed receipt response use controlled responses; purchases and the service outage/recreation check use real services. The tests verify that catalog errors survive searching and that receipt failures cannot resubmit a saved order. Screenshots and a print PDF go to the system temporary directory. Browser copy/print availability depends on browser permissions and OS support.

Stop test containers without deleting volumes:

```powershell
docker compose -p campus-bookstore-tests -f compose.yaml -f compose.test.yaml stop
```

## Service boundaries

| Service | Demo | Isolated tests | Storage |
| --- | --- | --- | --- |
| Storefront / nginx | localhost:3000 | localhost:3100 | Static files only |
| Product API | localhost:5201 | localhost:5301 | Own SQLite volume |
| Order API | localhost:5202 | localhost:5302 | Own PostgreSQL database |
| PostgreSQL | localhost:5432 | localhost:55432 | Separate demo/test volumes |

nginx proxies same-origin `/api/products`, `/api/quotes/`, and `/api/orders` requests. Order Service obtains product details through Product Service HTTP endpoints; neither service reads the other's database. `GET /products` returns `{ "products": [...] }` with newest products first. Other API behaviour is preserved.

The client disables repeat submissions while saving. If an order response is interrupted, it warns that the order may have been saved and locks that checkout attempt. If saving succeeds but receipt retrieval fails, it displays the saved order number for lookup without placing another order. The API has no server-side idempotency key, authentication, payment processing, or multi-product cart; these remain outside this demo.

Keep volumes when stopping the demo (`docker compose stop`) to preserve products and receipts. Changes are left uncommitted for local review.

## Review checks and Kubernetes prerequisites

For Docker Desktop Kubernetes monitoring setup, the node-exporter repair, and
commands to open Grafana, Prometheus, and Loki, see [monitoring/README.md](monitoring/README.md).

CI runs service unit tests, real PostgreSQL integration tests, browser regressions, and offline manifest checks with locked Node test dependencies. The nginx proxy refreshes Docker service DNS after container recreation. Product database failures return JSON 503 responses; malformed Product Service responses are rejected by Order Service with JSON 502 responses before an order is written.

The Kubernetes folder includes the PostgreSQL schema ConfigMap and validates its SQL against the Compose schema. Offline checks validate YAML and local resource references; they are not a cluster deployment or full API-server schema validation. The `orders-db-secret` secret (key `POSTGRES_PASSWORD`) and the `monitoring` namespace remain external prerequisites. No credentials are checked in. Existing database volumes retain their data; initialization SQL runs only for a new database.

The `deploy_local.py` watcher deploys the complete application from an exact
successful master push CI commit. The optional GitHub Actions `deploy-local` job
uses a registered Windows runner; see docs/CICD.md for the required repository
variable and runner label. Local files alone do not register a runner or publish
changes. Do not treat the unauthenticated local demo as a production deployment.
