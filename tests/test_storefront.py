"""Integration coverage through the storefront's same-origin API proxy."""
import json
import os
import unittest
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from test_support import test_url

BASE = test_url("STOREFRONT_URL", 3100)


def request(path, payload=None):
    req = Request(
        BASE + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=15) as response:
        return response.status, json.load(response)


class StorefrontTests(unittest.TestCase):
    def test_catalog_quote_order_and_saved_receipt(self):
        with urlopen(BASE, timeout=15) as response:
            self.assertIn(b"The Campus Bookstore", response.read())
        status, product = request("/api/products", {"name": "Storefront test notebook", "price_cad": "4.50"})
        self.assertEqual(status, 201)
        _, catalog = request("/api/products")
        self.assertIn(product, catalog["products"])
        _, saved_product = request(f"/api/products/{product['id']}")
        self.assertEqual(saved_product, product)
        _, quote = request(f"/api/quotes/{product['id']}?quantity=2")
        self.assertEqual(quote["total_cad"], "9.00")
        status, order = request("/api/orders", {"product_id": product["id"], "quantity": 2})
        self.assertEqual(status, 201)
        _, receipt = request(f"/api/orders/{order['order_id']}")
        self.assertEqual(receipt, order)
        self.assertEqual(receipt["total_cad"], "9.00")
        self.assertEqual(receipt["currency"], "CAD")
        result = subprocess.run(
            ["docker", "compose", "-p", "campus-bookstore-tests", "-f", "compose.yaml", "-f", "compose.test.yaml",
             "exec", "-T", "orders-db", "psql", "-U", "bookstore", "-d", "bookstore_orders", "-At", "-F", "|",
             "-c", f"SELECT product_id, product_name, quantity, unit_price_cents, currency FROM orders WHERE id = {int(order['order_id'])}"],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.strip(), f"{product['id']}|Storefront test notebook|2|450|CAD")

    def test_missing_receipt_and_invalid_quantity(self):
        for path, expected in [("/api/orders/9223372036854775807", 404), ("/api/quotes/1?quantity=0", 400)]:
            with self.assertRaises(HTTPError) as error:
                request(path)
            with error.exception as response:
                self.assertEqual(response.code, expected)
                self.assertIn("error", json.load(response))

    def test_unknown_product_and_zero_quantity_are_rejected(self):
        for path, payload, expected in [
            ("/api/products/9223372036854775807", None, 404),
            ("/api/quotes/9223372036854775807?quantity=2", None, 404),
            ("/api/orders", {"product_id": 9223372036854775807, "quantity": 2}, 404),
            ("/api/orders", {"product_id": 1, "quantity": 0}, 400),
        ]:
            with self.assertRaises(HTTPError) as error:
                request(path, payload)
            with error.exception as response:
                self.assertEqual(response.code, expected)
                self.assertIn("error", json.load(response))
