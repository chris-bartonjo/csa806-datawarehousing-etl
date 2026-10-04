"""ETL demo: CSV sources -> clean -> SQLite star schema (warehouse.db).

Each step is called on its own by app.py when you click Run in the web UI.
"""
import csv
import sqlite3
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"
DB_PATH = BASE / "warehouse.db"
DATE_FORMAT = "%d-%m-%Y"  # standard date format after Transform: dd-mm-yyyy

# Enrichment lookup: the source only has a city, the warehouse also wants a region.
CITY_REGION = {
    "Nairobi": "Nairobi",
    "Mombasa": "Coast",
    "Kisumu": "Nyanza",
    "Nakuru": "Rift Valley",
}


# ---------------------------------------------------------------- EXTRACT
def extract():
    with open(DATA / "sales_raw.csv", newline="", encoding="utf-8") as f:
        sales = list(csv.DictReader(f))
    with open(DATA / "products.csv", newline="", encoding="utf-8") as f:
        products = list(csv.DictReader(f))
    return sales, products


# -------------------------------------------------------------- TRANSFORM
def parse_date(text):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    return None


def transform(sales, products):
    catalog = {p["product_id"]: {**p, "unit_price": float(p["unit_price"])} for p in products}
    clean, rejected = [], []
    changes = []  # (transaction_id, field, before, after) for every value we fixed
    seen = set()

    for row in sales:
        tid = row["transaction_id"].strip()
        if tid in seen:
            rejected.append((tid, "duplicate transaction"))
            continue
        seen.add(tid)

        sale_date = parse_date(row["date"])
        if sale_date is None:
            rejected.append((tid, "unparseable date"))
            continue

        qty_text = row["quantity"].strip()
        if not qty_text:
            rejected.append((tid, "missing quantity"))
            continue
        qty = int(qty_text)
        if qty <= 0:
            rejected.append((tid, "non-positive quantity"))
            continue

        product = catalog.get(row["product_id"].strip())
        if product is None:
            rejected.append((tid, "unknown product"))
            continue

        date_text = sale_date.strftime(DATE_FORMAT)
        if row["date"] != date_text:
            changes.append((tid, "date", row["date"], date_text))
        city = row["store_city"].strip().title()
        if row["store_city"] != city:
            changes.append((tid, "store_city", row["store_city"], city))
        clean.append({
            "transaction_id": tid,
            "date": date_text,
            "city": city,
            "region": CITY_REGION.get(city, "Unknown"),
            "product_id": product["product_id"],
            "quantity": qty,
            "revenue": qty * product["unit_price"],  # derived measure
        })

    return clean, rejected, catalog, changes


# ------------------------------------------------------------------- LOAD
# Star schema: every dimension is one flat table, one join away from the fact table.
TABLES = ("dim_date", "dim_product", "dim_store", "fact_sales")

SCHEMA = """
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_store;

CREATE TABLE dim_date (
    date_key   INTEGER PRIMARY KEY,   -- YYYYMMDD
    full_date  TEXT NOT NULL,         -- dd-mm-yyyy
    day        INTEGER NOT NULL,
    month      INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    quarter    INTEGER NOT NULL,
    year       INTEGER NOT NULL
);
CREATE TABLE dim_product (
    product_key INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  TEXT UNIQUE NOT NULL,  -- natural key from source
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    unit_price  REAL NOT NULL
);
CREATE TABLE dim_store (
    store_key INTEGER PRIMARY KEY AUTOINCREMENT,
    city      TEXT UNIQUE NOT NULL,
    region    TEXT NOT NULL
);
CREATE TABLE fact_sales (
    transaction_id TEXT PRIMARY KEY,
    date_key       INTEGER NOT NULL REFERENCES dim_date(date_key),
    product_key    INTEGER NOT NULL REFERENCES dim_product(product_key),
    store_key      INTEGER NOT NULL REFERENCES dim_store(store_key),
    quantity       INTEGER NOT NULL,
    revenue        REAL NOT NULL
);
"""


def load(clean, catalog):
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)

    def date_key(text):  # dd-mm-yyyy -> YYYYMMDD integer (sorts chronologically)
        return int(datetime.strptime(text, DATE_FORMAT).strftime("%Y%m%d"))

    for text in sorted({r["date"] for r in clean}, key=date_key):
        d = datetime.strptime(text, DATE_FORMAT).date()
        con.execute(
            "INSERT INTO dim_date VALUES (?,?,?,?,?,?,?)",
            (date_key(text), text, d.day, d.month,
             d.strftime("%b"), (d.month - 1) // 3 + 1, d.year),
        )
    for p in catalog.values():
        con.execute(
            "INSERT INTO dim_product (product_id, name, category, unit_price) VALUES (?,?,?,?)",
            (p["product_id"], p["name"], p["category"], p["unit_price"]),
        )
    for city, region in sorted({(r["city"], r["region"]) for r in clean}):
        con.execute("INSERT INTO dim_store (city, region) VALUES (?,?)", (city, region))

    # Surrogate key lookups: natural key -> warehouse key
    product_key = dict(con.execute("SELECT product_id, product_key FROM dim_product"))
    store_key = dict(con.execute("SELECT city, store_key FROM dim_store"))

    con.executemany(
        "INSERT INTO fact_sales VALUES (?,?,?,?,?,?)",
        [(r["transaction_id"], date_key(r["date"]),
          product_key[r["product_id"]], store_key[r["city"]],
          r["quantity"], r["revenue"]) for r in clean],
    )
    con.commit()
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}
    con.close()
    return counts
