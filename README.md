# csa806-datawarehousing-etl

CSA806 Module 2 (Data Warehousing): an end-to-end **ETL** demo on retail sales data, built twice to compare
two warehouse designs. Each folder is a **self-contained project** with its own data, pipeline, reports and web UI.

| Project | Schema | Tables | Dashboard |
|---|---|---|---|
| [`star_schema/`](star_schema/) | Star: flat dimensions | 4 (`fact_sales` + 3 dims) | http://127.0.0.1:8000 |
| [`snowflake_schema/`](snowflake_schema/) | Snowflake: dimensions normalised into hierarchies | 7 (`fact_sales` + 6 dims) | http://127.0.0.1:8001 |

Both use the same source data and the same Extract and Transform steps. Only **Load** (the schema) and the
report **SQL** differ, and the report numbers come out identical.

## Star vs snowflake

### Star

```mermaid
erDiagram
    dim_date    ||--o{ fact_sales : date_key
    dim_product ||--o{ fact_sales : product_key
    dim_store   ||--o{ fact_sales : store_key

    fact_sales {
        text transaction_id PK
        int  date_key FK
        int  product_key FK
        int  store_key FK
        int  quantity
        real revenue
    }
    dim_date {
        int  date_key PK "YYYYMMDD"
        text full_date "dd-mm-yyyy"
        int  day
        int  month
        text month_name
        int  quarter
        int  year
    }
    dim_product {
        int  product_key PK
        text product_id "natural key"
        text name
        text category
        real unit_price
    }
    dim_store {
        int  store_key PK
        text city
        text region
    }
```

### Snowflake

```mermaid
erDiagram
    dim_month    ||--o{ dim_date    : month_key
    dim_category ||--o{ dim_product : category_key
    dim_region   ||--o{ dim_store   : region_key
    dim_date     ||--o{ fact_sales  : date_key
    dim_product  ||--o{ fact_sales  : product_key
    dim_store    ||--o{ fact_sales  : store_key

    fact_sales {
        text transaction_id PK
        int  date_key FK
        int  product_key FK
        int  store_key FK
        int  quantity
        real revenue
    }
    dim_date {
        int  date_key PK "YYYYMMDD"
        text full_date "dd-mm-yyyy"
        int  day
        int  month_key FK
    }
    dim_month {
        int  month_key PK "YYYYMM"
        int  month
        text month_name
        int  quarter
        int  year
    }
    dim_product {
        int  product_key PK
        text product_id "natural key"
        text name
        real unit_price
        int  category_key FK
    }
    dim_category {
        int  category_key PK
        text category_name
    }
    dim_store {
        int  store_key PK
        text city
        int  region_key FK
    }
    dim_region {
        int  region_key PK
        text region_name
    }
```

| | Star | Snowflake |
|---|---|---|
| Dimension design | Denormalised (category on each product) | Normalised (category in its own table) |
| Joins for "revenue by category" | 1 | 2 |
| Redundancy | Higher | Lower |
| Query simplicity and speed | Simpler, faster | More joins |
| Typical use | Most BI / reporting warehouses | Large or frequently changing hierarchies |

## Run a project

**macOS / Linux**

```bash
cd star_schema            # or snowflake_schema
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # once
.venv/bin/uvicorn app:app --reload                                   # add --port 8001 for snowflake
```

**Windows (PowerShell or Command Prompt)**

```powershell
cd star_schema            # or snowflake_schema
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt               # once
.venv\Scripts\python -m uvicorn app:app --reload                      # add --port 8001 for snowflake
```

See each project's README for details.
