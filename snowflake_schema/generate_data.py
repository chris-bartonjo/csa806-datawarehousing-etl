"""Generate dummy source CSVs for the ETL demo.

Produces ~100 sales transactions spanning Jan-Dec 2026, with data-quality
problems planted on purpose so the Transform step has something to fix:
  - duplicate transaction rows
  - mixed date formats (YYYY-MM-DD and DD/MM/YYYY)
  - messy city names (whitespace, wrong case)
  - missing and negative quantities
  - product IDs that don't exist in the catalog
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(806)  # fixed seed -> same data on every run

DATA = Path(__file__).parent / "data"

PRODUCTS = [
    ("P001", "Laptop", "Electronics", 85000),
    ("P002", "Smartphone", "Electronics", 30000),
    ("P003", "Headphones", "Electronics", 4500),
    ("P004", "Office Chair", "Furniture", 12000),
    ("P005", "Desk", "Furniture", 18000),
    ("P006", "Coffee Maker", "Appliances", 7500),
    ("P007", "Blender", "Appliances", 5000),
]
CITIES = ["Nairobi", "Nairobi", "Nairobi", "Mombasa", "Mombasa", "Kisumu", "Nakuru"]
CLEAN_ROWS = 92


def messy_city(city):
    return random.choice([city, city.upper(), city.lower(), f"  {city}", f"{city} "])


def write_products():
    with open(DATA / "products.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "name", "category", "unit_price"])
        w.writerows(PRODUCTS)


def write_sales():
    start = date(2026, 1, 1)
    rows = []
    for i in range(CLEAN_ROWS):
        d = start + timedelta(days=random.randint(0, 364))
        city = random.choice(CITIES)
        rows.append({
            "transaction_id": f"T{1001 + i}",
            "date": d.strftime("%d/%m/%Y") if random.random() < 0.2 else d.isoformat(),
            "store_city": messy_city(city) if random.random() < 0.25 else city,
            "product_id": random.choice(PRODUCTS)[0],
            "quantity": str(random.randint(1, 8)),
        })

    # Plant bad rows by corrupting a few existing ones.
    picks = random.sample(range(CLEAN_ROWS), 6)
    for i in picks[:3]:
        rows[i]["quantity"] = ""
    for i in picks[3:5]:
        rows[i]["quantity"] = str(-random.randint(1, 3))
    rows[picks[5]]["product_id"] = "P999"
    rows.append({**random.choice(rows), "transaction_id": f"T{1001 + CLEAN_ROWS}",
                 "product_id": "P888"})

    # Duplicates: exact copies of existing rows.
    rows += [dict(r) for r in random.sample(rows, 6)]

    rows.sort(key=lambda r: r["transaction_id"])
    with open(DATA / "sales_raw.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    write_products()
    n = write_sales()
    print(f"Wrote data/products.csv ({len(PRODUCTS)} rows) and data/sales_raw.csv ({n} rows)")
