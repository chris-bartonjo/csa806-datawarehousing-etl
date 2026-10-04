"""Print analytical reports from warehouse.db.  Run after etl.py."""
from queries import QUERIES, query


def print_table(title, rows):
    print(f"\n== {title} ==")
    if not rows:
        print("  (no rows)")
        return
    cols = list(rows[0])
    widths = [max(len(c), *(len(f"{r[c]:,}" if isinstance(r[c], (int, float)) else str(r[c])) for r in rows)) for c in cols]
    numeric = [isinstance(rows[0][c], (int, float)) for c in cols]
    print("  " + "  ".join(c.rjust(w) if n else c.ljust(w) for c, w, n in zip(cols, widths, numeric)))
    for r in rows:
        cells = [f"{r[c]:,}" if isinstance(r[c], (int, float)) else str(r[c]) for c in cols]
        print("  " + "  ".join(v.rjust(w) if isinstance(r[c], (int, float)) else v.ljust(w)
                               for v, w, c in zip(cells, widths, cols)))


if __name__ == "__main__":
    for name in QUERIES:
        print_table(name.replace("_", " ").title(), query(name))
