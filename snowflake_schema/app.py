"""FastAPI backend: runs each ETL step on demand and serves the UI.

Run:  .venv/bin/uvicorn app:app --reload --port 8001   ->  http://127.0.0.1:8001

Extract and Transform results are kept in memory (a "staging area") between
calls, so each step can be run and inspected on its own from the browser.
"""
import textwrap
from collections import Counter
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

import etl
from queries import QUERIES, WAREHOUSE_TABLES, query, table_preview, warehouse_ready

app = FastAPI(title="ETL Demo - Sales Warehouse (Snowflake Schema)")
STATIC = Path(__file__).parent / "static"

staging = {}  # pipeline data handed from one step to the next
results = {}  # last response of each step, so a page refresh can show it again


def load_result():
    if not warehouse_ready():
        return None
    return {"tables": [table_preview(t) for t in WAREHOUSE_TABLES]}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/state")
def state():
    return {"extract": results.get("extract"),
            "transform": results.get("transform"),
            "load": load_result()}


@app.post("/api/extract")
def extract():
    sales, products = etl.extract()
    staging.clear()
    results.clear()  # a fresh extract invalidates the old transform
    staging.update(sales=sales, products=products)
    results["extract"] = {"sales": sales, "products": products}
    return results["extract"]


@app.post("/api/transform")
def transform():
    if "sales" not in staging:
        raise HTTPException(400, "Run Extract first.")
    clean, rejected, catalog, changes = etl.transform(staging["sales"], staging["products"])
    staging.update(clean=clean, catalog=catalog)
    results["transform"] = {
        "rows_in": len(staging["sales"]),
        "clean": clean,
        "rejected": [{"transaction_id": t, "reason": r} for t, r in rejected],
        "rejected_by_reason": dict(Counter(r for _, r in rejected)),
        "changes": [{"transaction_id": t, "field": f, "before": b, "after": a}
                    for t, f, b, a in changes],
    }
    return results["transform"]


@app.post("/api/load")
def load():
    if "clean" not in staging:
        raise HTTPException(400, "Run Transform first.")
    etl.load(staging["clean"], staging["catalog"])
    return load_result()


@app.post("/api/reset")
def reset():
    """Clear the staging area and delete warehouse.db so the steps can be rerun."""
    staging.clear()
    results.clear()
    etl.DB_PATH.unlink(missing_ok=True)
    return state()


@app.get("/api/dashboard")
def dashboard():
    if not warehouse_ready():
        return {"empty": True}
    data = {name: query(name) for name in QUERIES}
    data["kpis"] = data["kpis"][0]
    data["sql"] = {name: textwrap.dedent(sql).strip() for name, sql in QUERIES.items()}
    return data
