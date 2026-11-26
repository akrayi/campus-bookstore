"""Verify real metrics labeling and failed-readiness behavior without demo data."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(service):
    spec = importlib.util.spec_from_file_location(service.replace('-', '_') + '_metrics_test', ROOT / service / 'app.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ObservabilityTests(unittest.TestCase):
    def test_metrics_use_route_templates_not_ids_or_query_strings(self):
        for name in ('product-service', 'order-service'):
            app = load(name)
            client = app.app.test_client()
            client.get('/does-not-exist/98765?secret=do-not-record')
            text = client.get('/metrics').get_data(as_text=True)
            self.assertIn('bookstore_http_requests_total', text)
            self.assertIn('route="unmatched"', text)
            self.assertIn('status="404"', text)
            self.assertNotIn('route="/does-not-exist/98765"', text)
            self.assertNotIn('do-not-record', text)

    def test_order_readiness_fails_when_database_is_unavailable(self):
        app = load('order-service')
        with patch.object(app, 'connect_db', side_effect=app.psycopg.OperationalError('offline')):
            self.assertEqual(app.app.test_client().get('/ready').status_code, 503)
        self.assertEqual(app.app.test_client().get('/health').status_code, 200)

    def test_metrics_scrapes_do_not_count_themselves(self):
        app = load('product-service')
        client = app.app.test_client()
        before = client.get('/metrics').data
        after = client.get('/metrics').data
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
