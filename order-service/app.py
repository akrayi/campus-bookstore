import json
import os
import re
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import psycopg
from flask import Flask, request

app = Flask(__name__)

PRODUCT_SERVICE_URL = os.getenv(
    "PRODUCT_SERVICE_URL", "http://127.0.0.1:5001"
).rstrip("/")


class InvalidProductResponse(Exception):
    pass


@app.errorhandler(InvalidProductResponse)
def handle_invalid_product_response(error):
    return {"error": "Product Service returned invalid product data."}, 502


def connect_db():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "bookstore_orders"),
        user=os.getenv("POSTGRES_USER", "bookstore"),
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    )


def fetch_product(product_id):
    url = f"{PRODUCT_SERVICE_URL}/products/{product_id}"
    with urlopen(url, timeout=3) as response:
        try:
            product = json.load(response)
        except (ValueError, UnicodeError) as error:
            raise InvalidProductResponse() from error

    if (
        not isinstance(product, dict)
        or type(product.get("id")) is not int
        or product["id"] != product_id
        or not isinstance(product.get("name"), str)
        or not product["name"].strip()
        or product.get("currency") != "CAD"
        or not isinstance(product.get("price_cad"), str)
        or not re.fullmatch(r"[0-9]{1,17}(?:\.[0-9]{1,2})?", product["price_cad"])
        or Decimal(product["price_cad"]) * 100 > 2**63 - 1
    ):
        raise InvalidProductResponse()
    return product


@app.errorhandler(HTTPError)
def handle_product_error(error):
    error.close()
    if error.code == 404:
        return {"error": "Product not found."}, 404
    return {"error": "Product Service returned an error."}, 502


@app.errorhandler(URLError)
@app.errorhandler(TimeoutError)
def handle_connection_error(error):
    return {"error": "Product Service is unavailable."}, 503


@app.errorhandler(psycopg.OperationalError)
def handle_database_error(error):
    return {"error": "Orders database is unavailable."}, 503


def format_cad(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def order_details(product_id, name, quantity, unit_cents):
    return {
        "product_id": product_id,
        "name": name,
        "quantity": quantity,
        "currency": "CAD",
        "unit_price_cad": format_cad(unit_cents),
        "total_cad": format_cad(unit_cents * quantity),
    }


def valid_quantity(quantity):
    return type(quantity) is int and 1 <= quantity <= 2_147_483_647


@app.get("/health")
def health():
    return {"service": "order-service", "status": "ok"}


@app.get("/quotes/<int:product_id>")
def get_quote(product_id):
    try:
        quantity = int(request.args.get("quantity", "1"))
    except ValueError:
        quantity = None

    if not valid_quantity(quantity):
        return {"error": "Enter a positive whole-number quantity within range."}, 400

    product = fetch_product(product_id)
    unit_cents = int(Decimal(product["price_cad"]) * 100)
    return order_details(product_id, product["name"], quantity, unit_cents)


@app.post("/orders")
def create_order():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {"error": "Send a JSON object with product_id and quantity."}, 400

    product_id = data.get("product_id")
    quantity = data.get("quantity")

    if type(product_id) is not int or not 1 <= product_id <= 2**63 - 1:
        return {"error": "Enter a valid positive product_id."}, 400
    if not valid_quantity(quantity):
        return {"error": "Enter a positive whole-number quantity within range."}, 400

    product = fetch_product(product_id)
    unit_cents = int(Decimal(product["price_cad"]) * 100)

    with connect_db() as conn:
        row = conn.execute(
            """
            INSERT INTO orders
                (product_id, product_name, quantity, unit_price_cents, currency)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (product_id, product["name"], quantity, unit_cents, "CAD"),
        ).fetchone()

    order_id = row[0]
    result = order_details(product_id, product["name"], quantity, unit_cents)
    result["order_id"] = order_id
    return result, 201, {"Location": f"/orders/{order_id}"}


@app.get("/orders/<int:order_id>")
def get_order(order_id):
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT product_id, product_name, quantity, unit_price_cents
            FROM orders
            WHERE id = %s
            """,
            (order_id,),
        ).fetchone()

    if row is None:
        return {"error": "Order not found."}, 404

    result = order_details(*row)
    result["order_id"] = order_id
    return result
