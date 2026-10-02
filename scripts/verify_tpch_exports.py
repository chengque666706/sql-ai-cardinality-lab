"""Verify exported CSV values and counts against the generated DuckDB tables."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".python_deps"))
import duckdb

folder = ROOT / "data" / "tpch_sf1"
metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
con = duckdb.connect(str(folder / "tpch.duckdb"), read_only=True)
con.execute("SET threads=4")
results = {}
for table, table_meta in metadata["tables"].items():
    def literal(text):
        return "'" + text.replace("'", "''") + "'"
    columns = "{" + ", ".join(literal(c["name"]) + ": " + literal(c["type"]) for c in table_meta["columns"]) + "}"
    csv_relation = f"read_csv({literal((folder / table_meta['file']).as_posix())}, delim='|', header=false, nullstr='\\N', columns={columns})"
    source = con.execute(f"SELECT count(*), bit_xor(hash(t)) FROM {table} t").fetchone()
    exported = con.execute(f"SELECT count(*), bit_xor(hash(t)) FROM {csv_relation} t").fetchone()
    assert source == exported, (table, source, exported)
    results[table] = {"source_rows": source[0], "csv_rows": exported[0], "source_row_hash_xor": source[1], "csv_row_hash_xor": exported[1], "match": True}
    print(table, source[0], "verified", flush=True)
con.close()
(folder / "csv_verification.json").write_text(json.dumps({"method": "Compare row count and order-independent XOR of DuckDB hashes of typed row structs. This is a content consistency check, not a cryptographic proof.", "duckdb_version": duckdb.__version__, "tables": results}, indent=2) + "\n", encoding="utf-8")
