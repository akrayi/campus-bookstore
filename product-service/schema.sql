CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0)
);