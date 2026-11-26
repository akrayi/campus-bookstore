# Start to stop in VS Code Command Prompt

Use VS Code Terminal > New Terminal > dropdown > Command Prompt. These commands
use CMD syntax. Start Docker Desktop with Linux containers and Kubernetes enabled.
Use the Kubernetes website for the final demo so its traffic appears in monitoring.

## First setup or after changing source

```cmd
cd /d C:\Users\aksha\campus-bookstore
docker info
kubectl config current-context
python scripts/init_env.py
python scripts/setup_cluster.py
python scripts/deploy.py
python scripts/setup_monitoring.py
python scripts/verify_cluster.py
```

The context must be docker-desktop. init_env creates a random ignored .env only
when one does not exist. deploy preserves an existing database Secret and PVCs,
builds the website and APIs before applying manifests, validates with the server,
then waits for all four deployments. Local source changes produce a content-based
image tag. Do not change existing database passwords to fix a startup error.
setup_cluster installs kube-router firewall-only and preserves a working
metrics-server. A fresh metrics-server uses local-only insecure kubelet TLS;
reconsider that setting outside Docker Desktop. No cloud cluster is targeted.

## Every demonstration

```cmd
cd /d C:\Users\aksha\campus-bookstore
kubectl --context docker-desktop get pods -n campus-bookstore
kubectl --context docker-desktop get pods -n monitoring
scripts\start_demo.cmd
```

The script opens three labeled CMD windows. Keep them open. Open these addresses:

| Address | What to show |
| --- | --- |
| http://localhost:3002 | Kubernetes bookstore website |
| http://localhost:3001/d/campus-bookstore | Campus Bookstore Grafana dashboard |
| http://localhost:9090 | Prometheus query page and target health |

For manual access, run each command in a separate terminal:

```cmd
kubectl --context docker-desktop port-forward -n campus-bookstore svc/storefront 3002:80
kubectl --context docker-desktop port-forward -n monitoring svc/bookstore-monitoring-grafana 3001:80
kubectl --context docker-desktop port-forward -n monitoring svc/bookstore-monitoring-kube-prometheus 9090:9090
```

If an address already works, keep the existing tunnel instead of starting another.
After a pod replacement, restart its tunnel if the connection closes.

## Seed the Kubernetes catalog explicitly

The environments keep separate data. With port 3002 forwarded:

```cmd
set DEMO_PRODUCT_URL=http://127.0.0.1:3002/api
python scripts/seed_demo.py
set DEMO_PRODUCT_URL=
```

This intentionally adds six example products through the API; sequential repeats
skip existing names. It never updates or removes existing products.

## Grafana and Prometheus

Grafana username is admin. Retrieve its generated password in a private terminal:

```cmd
kubectl --context docker-desktop get secret bookstore-monitoring-grafana -n monitoring -o jsonpath="{.data.admin-password}" | python -c "import sys,base64; print(base64.b64decode(sys.stdin.read()).decode())"
```

Open Dashboards > Campus Bookstore. Browse products and place an order on port
3002, then allow 30-120 seconds for scrapes and rate calculations. The dashboard
shows API request rate, p95 latency, server errors, pod CPU/memory, desired Order
replicas, and logs. No error series may appear until an error has occurred.

Explore > Loki > Code:

```logql
{namespace="campus-bookstore"}
```

Replace the whole query. Do not prepend `{}` or `|=`. Select Last 1 hour and Run.
For numeric queries select Prometheus, not the built-in -- Grafana -- test source:

```promql
up
sum by (service) (rate(bookstore_http_requests_total[2m]))
kube_pod_status_phase{namespace="campus-bookstore",phase="Running"}
```

## Demonstrate security and scaling

```cmd
python scripts/verify_cluster.py
python scripts/demo_scaling.py
kubectl --context docker-desktop get hpa -n campus-bookstore
```

verify_cluster fails if a forbidden connection is allowed; it checks both denied
and allowed paths. demo_scaling generates bounded CPU load without writing orders.
It observes the cluster for up to five minutes and fails if no scale-up is observed. Allow time for
scale-down after the remote load finishes. metrics-server is required for HPA;
Prometheus alone does not supply the CPU resource metrics.

Demonstrate a rolling update without changing business data:

```cmd
kubectl --context docker-desktop rollout restart deployment/order-service -n campus-bookstore
kubectl --context docker-desktop rollout status deployment/order-service -n campus-bookstore --timeout=180s
kubectl --context docker-desktop rollout history deployment/order-service -n campus-bookstore
```

maxUnavailable=0 keeps an old ready replica until a new one is ready. Product
Service deliberately uses Recreate for its SQLite volume; do not claim it is a
zero-downtime deployment.

## Inspect the Kubernetes orders database

```cmd
kubectl --context docker-desktop exec -n campus-bookstore deployment/orders-db -- psql -U bookstore -d bookstore_orders -P pager=off -c "SELECT id, product_name, quantity, created_at FROM orders ORDER BY id DESC;"
```

The old Compose demo remains available on port 3000 when started with
`docker compose up --build -d --wait`. It is not the same database as Kubernetes.
For that database use `docker compose exec orders-db psql -U bookstore -d bookstore_orders`.

## Stop and restart safely

Press Ctrl+C in the three port-forward windows. This stops browser access, not
the Kubernetes workloads. Stop any Compose demo or test stack separately:

```cmd
docker compose stop
docker compose -p campus-bookstore-tests -f compose.yaml -f compose.test.yaml stop
```

To stop Kubernetes and monitoring too, quit Docker Desktop after stopping the
tunnels. Next time start Docker Desktop, wait for the pods, then run
`scripts\start_demo.cmd`. Existing PVCs are retained. Do not delete namespaces,
PVCs or use `docker compose down --volumes` during a normal shutdown.

## If something fails

```cmd
kubectl --context docker-desktop get pods -n campus-bookstore
kubectl --context docker-desktop describe deployment/order-service -n campus-bookstore
kubectl --context docker-desktop logs deployment/order-service -n campus-bookstore --tail=60
kubectl --context docker-desktop logs daemonset/kube-router -n kube-system --tail=60
```

For port 3000 use `docker compose ps` and `docker compose logs --tail=60`.
For missing metrics allow two minutes, check /metrics through the internal API,
and check Prometheus target health. For editor-only errors reload VS Code; the
workspace associates Kubernetes manifests with the Kubernetes schema.
