import json
import os
import unittest
from urllib.request import Request, urlopen

PRODUCT_URL = os.getenv("PRODUCT_URL", "http://127.0.0.1:5201")
ORDER_URL = os.getenv("ORDER_URL", "http://127.0.0.1:5202")


class ServiceIntegrationTests(unittest.TestCase):
    def test_quote_uses_price_from_product_service(self):
        payload = {"name": "Integration Test Folder", "price_cad": "2.35"}
        request = Request(
            f"{PRODUCT_URL}/products",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(request, timeout=10) as response:
            self.assertEqual(response.status, 201)
            product_id = json.load(response)["id"]

        with urlopen(f"{ORDER_URL}/quotes/{product_id}?quantity=3", timeout=10) as response:
            self.assertEqual(response.status, 200)
            quote = json.load(response)

        self.assertEqual(quote["product_id"], product_id)
        self.assertEqual(quote["name"], payload["name"])
        self.assertEqual(quote["currency"], "CAD")
        self.assertEqual(quote["unit_price_cad"], "2.35")
        self.assertEqual(quote["total_cad"], "7.05")