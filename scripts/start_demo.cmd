@echo off
cd /d "%~dp0.."
kubectl --context docker-desktop get deployments -n campus-bookstore
if errorlevel 1 exit /b 1
start "Bookstore Kubernetes - Ctrl+C to close" cmd /k kubectl --context docker-desktop port-forward -n campus-bookstore svc/storefront 3002:80 --address 127.0.0.1
start "Grafana - Ctrl+C to close" cmd /k kubectl --context docker-desktop port-forward -n monitoring svc/bookstore-monitoring-grafana 3001:80 --address 127.0.0.1
start "Prometheus - Ctrl+C to close" cmd /k kubectl --context docker-desktop port-forward -n monitoring svc/bookstore-monitoring-kube-prometheus 9090:9090 --address 127.0.0.1
echo Bookstore: http://localhost:3002
echo Grafana: http://localhost:3001
echo Prometheus: http://localhost:9090
echo If an address already works, do not start a duplicate port-forward.
