"""Analytical queries over the snowflake schema. Shared by report.py and app.py."""
import sqlite3

from etl import DB_PATH, TABLES

# Snowflake: reaching a hierarchy attribute (category, region, month) takes an extra join.
QUERIES = {
    "kpis": """
        SELECT COUNT(*)                     AS transactions,
               SUM(quantity)                AS units,
               ROUND(SUM(revenue), 2)       AS revenue,
               ROUND(AVG(revenue), 2)       AS avg_order_value
        FROM fact_sales
    """,
    "revenue_by_month": """
        SELECT m.month, m.month_name, ROUND(SUM(f.revenue), 2) AS revenue
        FROM fact_sales f
        JOIN dim_date  d ON f.date_key  = d.date_key
        JOIN dim_month m ON d.month_key = m.month_key
        GROUP BY m.month_key, m.month, m.month_name ORDER BY m.month_key
    """,
    "revenue_by_category": """
        SELECT c.category_name AS category, ROUND(SUM(f.revenue), 2) AS revenue
        FROM fact_sales f
        JOIN dim_product  p ON f.product_key  = p.product_key
        JOIN dim_category c ON p.category_key = c.category_key
        GROUP BY c.category_name ORDER BY revenue DESC
    """,
    "revenue_by_store": """
        SELECT s.city, r.region_name AS region, ROUND(SUM(f.revenue), 2) AS revenue
        FROM fact_sales f
        JOIN dim_store  s ON f.store_key  = s.store_key
        JOIN dim_region r ON s.region_key = r.region_key
        GROUP BY s.city, r.region_name ORDER BY revenue DESC
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
