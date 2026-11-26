"""Bounded-label HTTP metrics; one Gunicorn worker per independently scaled pod."""
import logging
import time

from flask import Response, g, request
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


def instrument(app, service):
    registry = CollectorRegistry()
    requests = Counter('bookstore_http_requests_total', 'Completed API requests',
                       ['service', 'method', 'route', 'status'], registry=registry)
    latency = Histogram('bookstore_http_request_duration_seconds', 'API response time',
                        ['service', 'method', 'route'], registry=registry)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    @app.before_request
    def start_request():
        g.request_started = time.perf_counter()

    @app.after_request
    def record_request(response):
        if request.path not in {'/metrics', '/health', '/ready'}:
            # Never use raw paths, IDs, query strings or user input as metric labels.
            route = request.url_rule.rule if request.url_rule else 'unmatched'
            elapsed = time.perf_counter() - g.request_started
            requests.labels(service, request.method, route, str(response.status_code)).inc()
            latency.labels(service, request.method, route).observe(elapsed)
            app.logger.info('service=%s method=%s route=%s status=%s duration=%.6f',
                            service, request.method, route, response.status_code, elapsed)
        return response

    @app.get('/metrics')
    def metrics():
        return Response(generate_latest(registry), content_type=CONTENT_TYPE_LATEST)

    app.extensions['bookstore_metrics'] = registry
