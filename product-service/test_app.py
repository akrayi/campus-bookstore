import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import app as product_service


class ProductServiceTests(unittest.TestCase):
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