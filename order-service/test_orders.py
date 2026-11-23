import unittest
from unittest.mock import patch

import app as order_service


class OrderServiceTests(unittest.TestCase):
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