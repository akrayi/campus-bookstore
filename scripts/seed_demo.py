"""Add realistic demo products through the Product API; safe to rerun sequentially."""
import json
import os
from urllib.request import Request, urlopen

PRODUCT_URL = os.getenv("DEMO_PRODUCT_URL", "http://127.0.0.1:5201").rstrip("/")
DEMO_PRODUCTS = [
    ("The Study Skills Handbook", "24.95"),
    ("Introduction to Biology", "68.50"),
    ("Campus Ruled Notebook", "6.50"),
    ("Pocket Sketchbook", "9.75"),
    ("Everyday Gel Pens", "5.25"),
    ("Cedar Pencil Set", "4.50"),
]


def seed():
    with urlopen(f"{PRODUCT_URL}/products", timeout=15) as response:
        existing = {p["name"].strip().casefold() for p in json.load(response)["products"]}
    created = 0
    for name, price in DEMO_PRODUCTS:
        if name.casefold() in existing:
            print(f"Keep existing: {name}")
            continue
        request = Request(
            f"{PRODUCT_URL}/products",
            data=json.dumps({"name": name, "price_cad": price, "currency": "CAD"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=15) as response:
            product = json.load(response)
        existing.add(name.casefold())
        created += 1
        print(f"Added #{product['id']}: {name} (${price} CAD)")
    print(f"Created {created} demo products. Existing products were preserved.")


if __name__ == "__main__":
    seed()
