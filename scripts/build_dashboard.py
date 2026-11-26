"""Generate the version-controlled Grafana dashboard ConfigMap."""
import json
from pathlib import Path

queries = [
    ('API requests per second', 'sum by (service) (rate(bookstore_http_requests_total[2m]))'),
    ('API p95 latency (seconds)', 'histogram_quantile(0.95, sum by (le, service) (rate(bookstore_http_request_duration_seconds_bucket[2m])))'),
    ('Server errors per second', 'sum by (service) (rate(bookstore_http_requests_total{status=~"5.."}[2m]))'),
    ('Pod CPU cores', 'sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="campus-bookstore",container!="",container!="POD"}[2m]))'),
    ('Pod memory bytes', 'sum by (pod) (container_memory_working_set_bytes{namespace="campus-bookstore",container!="",container!="POD"})'),
    ('Order desired replicas', 'kube_horizontalpodautoscaler_status_desired_replicas{namespace="campus-bookstore"}'),
]
panels = []
for i, (title, query) in enumerate(queries):
    panels.append(dict(id=i+1, type='timeseries', title=title,
                       datasource=dict(type='prometheus', uid='prometheus'),
                       gridPos=dict(x=(i % 2)*12, y=(i // 2)*8, w=12, h=8),
                       targets=[dict(refId='A', expr=query)]))
panels.append(dict(id=7, type='logs', title='Bookstore pod logs',
                   datasource=dict(type='loki', uid='bookstore-loki'),
                   gridPos=dict(x=0, y=24, w=24, h=9),
                   targets=[dict(refId='A', expr='{namespace="campus-bookstore"}')],
                   options=dict(showTime=True, sortOrder='Descending')))
dashboard = dict(uid='campus-bookstore', title='Campus Bookstore', schemaVersion=39,
                 version=1, refresh='15s', time={'from': 'now-30m', 'to': 'now'}, panels=panels)
header = ('apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: bookstore-dashboard\n'
          '  namespace: monitoring\n  labels:\n    grafana_dashboard: "1"\n'
          'data:\n  bookstore.json: |\n')
path = Path(__file__).resolve().parents[1] / 'monitoring/dashboard.yaml'
path.write_text(header + '\n'.join('    ' + line for line in json.dumps(dashboard, indent=2).splitlines()) + '\n', encoding='utf-8')
print('Generated monitoring/dashboard.yaml')
