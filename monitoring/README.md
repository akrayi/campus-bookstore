# Local Kubernetes monitoring

This setup monitors the Docker Desktop Kubernetes cluster. Start Docker Desktop
with Kubernetes enabled. It does not collect logs from the separate Docker Compose
demo. Run commands from the repository root in PowerShell.

For the full monitored Kubernetes website, use port **3002** and the
[current CMD guide](../docs/DEMO-CMD.md). Run `python scripts/setup_monitoring.py`
to provision the complete stack, API ServiceMonitor, and **Campus Bookstore**
dashboard. `python scripts/deploy.py` deploys the instrumented APIs and website.
The steps below describe the individual monitoring components.

## Install or repair

Confirm the selected cluster before installing:

```powershell
kubectl config current-context
# Expected: docker-desktop
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm upgrade --install bookstore-monitoring prometheus-community/kube-prometheus-stack --version 93.9.0 --namespace monitoring --create-namespace -f monitoring/stack-values.yaml --wait --timeout 5m
kubectl apply -f monitoring/loki.yaml
helm upgrade --install bookstore-alloy grafana/alloy --version 1.16.0 --namespace monitoring -f monitoring/alloy-values.yaml --wait --timeout 5m
kubectl rollout status deployment/bookstore-loki -n monitoring --timeout=120s
```

`stack-values.yaml` fixes node-exporter's Docker Desktop mount-propagation error
with `mountPropagation: None`. The host root is still mounted read-only, but new
host submounts do not propagate. This file also disables the controller-manager,
scheduler, etcd, and kube-proxy scrapes because their metrics endpoints refuse
connections in this local cluster. Their corresponding rule groups are disabled.
These settings are specific to Docker Desktop; reassess them for another cluster.
Alertmanager remains disabled, so notification delivery is not configured.

## Open the tools

Keep each command running in its own PowerShell terminal. They bind to localhost.
Port 3001 avoids the storefront's port 3000.

```powershell
kubectl --context docker-desktop port-forward -n monitoring svc/bookstore-monitoring-grafana 3001:80 --address 127.0.0.1
```

Open http://localhost:3001. The default username is `admin`. Retrieve the
installation's generated password locally with the following command; treat its
output as a secret and do not paste it into chat or commit it:

```powershell
$grafanaPasswordBase64 = kubectl --context docker-desktop get secret bookstore-monitoring-grafana -n monitoring -o jsonpath='{.data.admin-password}'
[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($grafanaPasswordBase64))
```

In Grafana, open **Dashboards** and choose **Kubernetes / Compute Resources /
Namespace (Pods)**, then select `campus-bookstore` for namespace. For logs, open
**Explore**, select **Loki**, and run:

```logql
{namespace="campus-bookstore"}
```

Prometheus can also be opened directly:

```powershell
kubectl --context docker-desktop port-forward -n monitoring svc/bookstore-monitoring-kube-prometheus 9090:9090 --address 127.0.0.1
```

Open http://localhost:9090. Check **Status > Target health**, or query:

```promql
up
```

For bookstore pod status, query:

```promql
kube_pod_status_phase{namespace="campus-bookstore",phase="Running"}
```

Loki is normally queried through Grafana. For direct API access:

```powershell
kubectl --context docker-desktop port-forward -n monitoring svc/bookstore-loki 3100:3100 --address 127.0.0.1
```

http://localhost:3100/ready returns readiness; Loki has no standalone dashboard.
Press Ctrl+C in each terminal to close its port-forward. Monitoring keeps running
in Kubernetes. After a Docker Desktop restart, wait for the pods to recover and
run the port-forward commands again.

## Verify

```powershell
helm list -n monitoring
kubectl get pods -n monitoring
kubectl logs -n monitoring daemonset/bookstore-monitoring-prometheus-node-exporter --tail=20
kubectl logs -n monitoring deployment/bookstore-alloy -c alloy --tail=20
```

The exporter should be `1/1 Running`, and both Helm releases should be `deployed`.
Alloy collects pod logs only from the `campus-bookstore` namespace. Kubernetes
CPU/memory and pod status metrics are available. The updated Flask apps expose
`/metrics` with request counts and response-time histograms, discovered through
`monitoring/service-monitors.yaml`. `monitoring/dashboard.yaml` provisions API
request rate, latency, errors, CPU, memory, replicas and logs together. Metrics
use route templates instead of user IDs or query strings. `/health` tests the
process; `/ready` queries each API's own database table.

Prometheus currently uses ephemeral storage and keeps up to one day of metrics;
Grafana has no persistent volume in these values. Loki uses the existing 1 GiB
PVC. This is a local demo configuration.
