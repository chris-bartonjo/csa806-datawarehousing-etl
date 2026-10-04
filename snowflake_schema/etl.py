"""ETL demo: CSV sources -> clean -> SQLite snowflake schema (warehouse.db).

Run:  python3 etl.py
"""
import csv
import sqlite3
from collections import Counter
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
# Snowflake schema: dimensions are normalised into hierarchies.
#   dim_date    -> dim_month    (month, quarter, year)
#   dim_product -> dim_category
#   dim_store   -> dim_region
TABLES = ("dim_month", "dim_date", "dim_category", "dim_product",
          "dim_region", "dim_store", "fact_sales")

SCHEMA = """
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_month;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_category;
DROP TABLE IF EXISTS dim_store;
DROP TABLE IF EXISTS dim_region;

CREATE TABLE dim_month (
    month_key  INTEGER PRIMARY KEY,   -- YYYYMM
    month      INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    quarter    INTEGER NOT NULL,
    year       INTEGER NOT NULL
);
CREATE TABLE dim_date (
    date_key  INTEGER PRIMARY KEY,    -- YYYYMMDD
    full_date TEXT NOT NULL,          -- dd-mm-yyyy
    day       INTEGER NOT NULL,
    month_key INTEGER NOT NULL REFERENCES dim_month(month_key)
);
CREATE TABLE dim_category (
    category_key  INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT UNIQUE NOT NULL
);
CREATE TABLE dim_product (
    product_key  INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id   TEXT UNIQUE NOT NULL,  -- natural key from source
    name         TEXT NOT NULL,
    unit_price   REAL NOT NULL,
    category_key INTEGER NOT NULL REFERENCES dim_category(category_key)
);
CREATE TABLE dim_region (
    region_key  INTEGER PRIMARY KEY AUTOINCREMENT,
    region_name TEXT UNIQUE NOT NULL
);
CREATE TABLE dim_store (
    store_key  INTEGER PRIMARY KEY AUTOINCREMENT,
    city       TEXT UNIQUE NOT NULL,
    region_key INTEGER NOT NULL REFERENCES dim_region(region_key)
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

    def to_date(text):
        return datetime.strptime(text, DATE_FORMAT).date()

    def date_key(text):  # dd-mm-yyyy -> YYYYMMDD integer (sorts chronologically)
        return int(to_date(text).strftime("%Y%m%d"))

    # Outer levels of each hierarchy first, so the inner levels can reference them.
    dates = sorted({to_date(r["date"]) for r in clean})
    for d in sorted({(d.year, d.month) for d in dates}):
        year, month = d
        con.execute(
            "INSERT INTO dim_month VALUES (?,?,?,?,?)",
            (year * 100 + month, month, datetime(year, month, 1).strftime("%b"),
             (month - 1) // 3 + 1, year),
        )
    for d in dates:
        con.execute(
            "INSERT INTO dim_date VALUES (?,?,?,?)",
            (int(d.strftime("%Y%m%d")), d.strftime(DATE_FORMAT), d.day, d.year * 100 + d.month),
        )

    for category in sorted({p["category"] for p in catalog.values()}):
        con.execute("INSERT INTO dim_category (category_name) VALUES (?)", (category,))
    category_key = dict(con.execute("SELECT category_name, category_key FROM dim_category"))
    for p in catalog.values():
        con.execute(
            "INSERT INTO dim_product (product_id, name, unit_price, category_key) VALUES (?,?,?,?)",
            (p["product_id"], p["name"], p["unit_price"], category_key[p["category"]]),
        )

    for region in sorted({r["region"] for r in clean}):
        con.execute("INSERT INTO dim_region (region_name) VALUES (?)", (region,))
    region_key = dict(con.execute("SELECT region_name, region_key FROM dim_region"))
    for city, region in sorted({(r["city"], r["region"]) for r in clean}):
        con.execute("INSERT INTO dim_store (city, region_key) VALUES (?,?)",
                    (city, region_key[region]))

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


# -------------------------------------------------------------- PIPELINE
def run():
    sales, products = extract()
    clean, rejected, catalog, _ = transform(sales, products)
    tables = load(clean, catalog)
    return {
        "extracted": {"sales_raw.csv": len(sales), "products.csv": len(products)},
        "cleaned": len(clean),
        "rejected": [{"transaction_id": t, "reason": r} for t, r in rejected],
        "rejected_by_reason": dict(Counter(r for _, r in rejected)),
        "loaded": tables,
    }


if __name__ == "__main__":
    s = run()
    print("[EXTRACT]")
    for src, n in s["extracted"].items():
        print(f"  {src:<16} {n:>4} rows")
    print("[TRANSFORM]")
    print(f"  clean rows       {s['cleaned']:>4}")
    print(f"  rejected rows    {len(s['rejected']):>4}")
    for reason, n in s["rejected_by_reason"].items():
        print(f"    - {reason:<22} {n}")
    print(f"[LOAD] -> {DB_PATH.name}")
    for table, n in s["loaded"].items():
        print(f"  {table:<16} {n:>4} rows")
