import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from flask import Flask, request

app = Flask(__name__)
DATABASE_PATH = Path(os.getenv("PRODUCT_DB_PATH", Path(__file__).with_name("products.db")))
MAX_CENTS = 2**63 - 1


def product_response(product_id, name, cents):
    return {
        "id": product_id,
        "name": name,
        "price_cad": f"{cents // 100}.{cents % 100:02d}",
        "currency": "CAD",
    }


def read_price_cents(data):
    if "price_cad" in data and "price_cents" in data:
        raise ValueError("Send only one price field.")

    if "price_cad" in data:
        amount = data["price_cad"]
        if not isinstance(amount, str) or not re.fullmatch(
            r"[0-9]{1,17}(?:\.[0-9]{1,2})?", amount
        ):
            raise ValueError('Enter a CAD price as text, for example "4.50".')

        dollars, _, fraction = amount.partition(".")
        cents = int(dollars) * 100 + int(fraction.ljust(2, "0"))
    else:
        # Accept the original price_cents format for existing callers.
        cents = data.get("price_cents")

    if type(cents) is not int or not 0 <= cents <= MAX_CENTS:
        raise ValueError("Enter a valid non-negative CAD price.")

    return cents


@app.get("/health")
def health():
    return {"service": "product-service", "status": "ok"}


@app.post("/products")
def create_product():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {"error": "Send a JSON object with name and price_cad."}, 400

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return {"error": "Product name is required."}, 400

    if data.get("currency", "CAD") != "CAD":
        return {"error": "The bookstore accepts CAD prices only."}, 400

    try:
        cents = read_price_cents(data)
    except ValueError as error:
        return {"error": str(error)}, 400

    name = name.strip()
    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        cursor = db.execute(
            "INSERT INTO products (name, price_cents) VALUES (?, ?)",
            (name, cents),
        )
        db.commit()
        product_id = cursor.lastrowid

    return product_response(product_id, name, cents), 201


@app.get("/products/<int:product_id>")
def get_product(product_id):
    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        db.row_factory = sqlite3.Row
        product = db.execute(
            "SELECT id, name, price_cents FROM products WHERE id = ?",
            (str(product_id),),
        ).fetchone()

    if product is None:
        return {"error": "Product not found."}, 404

    return product_response(product["id"], product["name"], product["price_cents"]), 200