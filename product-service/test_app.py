import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import app as product_service


class ProductServiceTests(unittest.TestCase):
    def test_database_failure_returns_json(self):
        client = product_service.app.test_client()
        with patch.object(product_service.sqlite3, "connect", side_effect=sqlite3.OperationalError("locked")):
            for method, path, payload in [
                ("GET", "/products", None),
                ("GET", "/products/1", None),
                ("POST", "/products", {"name": "Notebook", "price_cad": "4.50"}),
            ]:
                with self.subTest(method=method, path=path):
                    response = client.open(path, method=method, json=payload)
                    self.assertEqual(response.status_code, 503)
                    self.assertIn("unavailable", response.get_json()["error"])

    def test_invalid_products_are_rejected_before_database_access(self):
        client = product_service.app.test_client()
        with patch.object(product_service.sqlite3, "connect") as connect:
            for data in [None, [], {}, {"name": "  ", "price_cad": "1.00"},
                         {"name": "Book", "price_cad": "1.005"},
                         {"name": "Book", "price_cents": True},
                         {"name": "Book", "price_cad": "1.00", "price_cents": 100},
                         {"name": "Book", "price_cad": "1.00", "currency": "USD"}]:
                with self.subTest(data=data):
                    self.assertEqual(client.post("/products", json=data).status_code, 400)
            connect.assert_not_called()

    def test_create_and_retrieve_cad_product(self):
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8-sig")

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "test.db"
            with closing(sqlite3.connect(database)) as db:
                db.executescript(schema)

            with patch.object(product_service, "DATABASE_PATH", database):
                client = product_service.app.test_client()
                created = client.post(
                    "/products",
                    json={"name": "Notebook", "price_cad": "4.50"},
                )
                self.assertEqual(created.status_code, 201)

                product_id = created.get_json()["id"]
                saved = client.get(f"/products/{product_id}")
                self.assertEqual(saved.status_code, 200)
                self.assertEqual(saved.get_json(), {
                    "id": product_id,
                    "name": "Notebook",
                    "price_cad": "4.50",
                    "currency": "CAD",
                })
                listing = client.get("/products")
                self.assertEqual(listing.status_code, 200)
                self.assertEqual(listing.get_json(), {"products": [saved.get_json()]})
