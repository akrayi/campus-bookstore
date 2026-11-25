import json
import os
import unittest
from urllib.request import Request, urlopen

from test_support import test_url

PRODUCT_URL = test_url("PRODUCT_URL", 5301)
ORDER_URL = test_url("ORDER_URL", 5302)


def post_json(url, payload):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return response.status, response.headers.get("Location"), json.load(response)


class BookstoreEndToEndTests(unittest.TestCase):
    def test_customer_can_place_and_retrieve_order(self):
        status, _, product = post_json(
            f"{PRODUCT_URL}/products",
            {"name": "E2E Sketchbook", "price_cad": "3.75"},
        )
        self.assertEqual(status, 201)

        status, location, order = post_json(
            f"{ORDER_URL}/orders",
            {"product_id": product["id"], "quantity": 2},
        )
        self.assertEqual(status, 201)
        self.assertEqual(location, f"/orders/{order['order_id']}")

        with urlopen(f"{ORDER_URL}{location}", timeout=10) as response:
            self.assertEqual(response.status, 200)
            saved_order = json.load(response)

        self.assertEqual(saved_order, order)
        self.assertEqual(saved_order["product_id"], product["id"])
        self.assertEqual(saved_order["name"], "E2E Sketchbook")
        self.assertEqual(saved_order["quantity"], 2)
        self.assertEqual(saved_order["currency"], "CAD")
        self.assertEqual(saved_order["unit_price_cad"], "3.75")
        self.assertEqual(saved_order["total_cad"], "7.50")
