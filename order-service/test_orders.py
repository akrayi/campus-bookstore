import unittest
import io
import json
from urllib.error import HTTPError, URLError
from unittest.mock import patch

import app as order_service


class OrderServiceTests(unittest.TestCase):
    def test_upstream_failures_return_json(self):
        client = order_service.app.test_client()
        for error, status in [(HTTPError("http://product", 404, "missing", {}, None), 404),
                              (HTTPError("http://product", 500, "failed", {}, None), 502),
                              (URLError("offline"), 503), (TimeoutError(), 503)]:
            with self.subTest(status=status), patch.object(order_service, "urlopen", side_effect=error):
                response = client.get("/quotes/1?quantity=2")
                self.assertEqual(response.status_code, status)
                self.assertIn("error", response.get_json())

    def test_invalid_upstream_product_never_creates_an_order(self):
        client = order_service.app.test_client()
        valid = {"id": 1, "name": "Notebook", "currency": "CAD", "price_cad": "4.50"}
        for product in [None, [], {}, {**valid, "id": 2}, {**valid, "currency": "USD"},
                        {**valid, "price_cad": "NaN"}, {**valid, "price_cad": "1.001"},
                        {**valid, "price_cad": "99999999999999999.99"}]:
            with self.subTest(product=product), patch.object(order_service, "connect_db") as connect:
                with patch.object(order_service, "urlopen", return_value=io.BytesIO(json.dumps(product).encode())):
                    response = client.post("/orders", json={"product_id": 1, "quantity": 2})
                self.assertEqual(response.status_code, 502)
                self.assertIn("error", response.get_json())
                connect.assert_not_called()
        with patch.object(order_service, "urlopen", return_value=io.BytesIO(b"not JSON")):
            self.assertEqual(client.get("/quotes/1").status_code, 502)

    def test_database_failure_returns_json(self):
        client = order_service.app.test_client()
        with patch.object(order_service, "connect_db", side_effect=order_service.psycopg.OperationalError("offline")):
            response = client.get("/orders/1")
            self.assertEqual(response.status_code, 503)
            self.assertIn("unavailable", response.get_json()["error"])

    def test_two_notebooks_cost_nine_cad(self):
        order = order_service.order_details(
            product_id=1,
            name="Notebook",
            quantity=2,
            unit_cents=450,
        )

        self.assertEqual(order["currency"], "CAD")
        self.assertEqual(order["unit_price_cad"], "4.50")
        self.assertEqual(order["total_cad"], "9.00")

    def test_zero_quantity_is_rejected_before_product_lookup(self):
        client = order_service.app.test_client()

        with patch.object(order_service, "fetch_product") as lookup:
            response = client.post(
                "/orders",
                json={"product_id": 1, "quantity": 0},
            )

        self.assertEqual(response.status_code, 400)
        lookup.assert_not_called()
