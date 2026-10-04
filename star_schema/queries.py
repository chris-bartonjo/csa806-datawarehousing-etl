"""Analytical queries over the star schema, served to the web UI by app.py."""
import sqlite3

from etl import DB_PATH, TABLES

QUERIES = {
    "kpis": """
        SELECT COUNT(*)                     AS transactions,
               SUM(quantity)                AS units,
               ROUND(SUM(revenue), 2)       AS revenue,
               ROUND(AVG(revenue), 2)       AS avg_order_value
        FROM fact_sales
    """,
    "revenue_by_month": """
        SELECT d.month, d.month_name, ROUND(SUM(f.revenue), 2) AS revenue
        FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY d.month, d.month_name ORDER BY d.month
    """,
    "revenue_by_category": """
        SELECT p.category, ROUND(SUM(f.revenue), 2) AS revenue
        FROM fact_sales f JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.category ORDER BY revenue DESC
    """,
    "revenue_by_store": """
        SELECT s.city, s.region, ROUND(SUM(f.revenue), 2) AS revenue
        FROM fact_sales f JOIN dim_store s ON f.store_key = s.store_key
        GROUP BY s.city, s.region ORDER BY revenue DESC
    """,
    "top_products": """
        SELECT p.name, SUM(f.quantity) AS units, ROUND(SUM(f.revenue), 2) AS revenue
        FROM fact_sales f JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.name ORDER BY revenue DESC
    """,
}


def query(name):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(QUERIES[name])]
    con.close()
    return rows


WAREHOUSE_TABLES = TABLES


def warehouse_ready():
    if not DB_PATH.exists():
        return False
    con = sqlite3.connect(DB_PATH)
    found = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fact_sales'").fetchone()
    con.close()
    return found is not None


def table_preview(table, limit=5):
    """Row count, columns and first few rows of a warehouse table."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    cur = con.execute(f"SELECT * FROM {table} LIMIT ?", (limit,))
    columns = [c[0] for c in cur.description]
    rows = [dict(r) for r in cur]
    con.close()
    return {"table": table, "count": count, "columns": columns, "rows": rows}
