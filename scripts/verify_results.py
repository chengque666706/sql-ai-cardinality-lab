"""Read-only audit of saved PostgreSQL plans and CSVs; standard library only.

Run: python scripts/verify_results.py
No database connection, Docker invocation, or writes are performed.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def same_number(text, expected, label: str) -> None:
    require(math.isclose(float(text), float(expected), rel_tol=1e-12, abs_tol=1e-12),
            f"Numeric mismatch: {label}: {text} != {expected}")


def flatten(node, path="0"):
    yield path, node
    for index, child in enumerate(node.get("Plans", [])):
        yield from flatten(child, f"{path}.{index}")


def shape(node):
    """Physical shape, excluding estimates, timings, buffers, and runtime rows."""
    return (node["Node Type"], node.get("Join Type"), node.get("Schema"),
            node.get("Relation Name"), node.get("Alias"), node.get("Index Name"),
            tuple(shape(child) for child in node.get("Plans", [])))


def main(root: Path) -> None:
    result_dir = root / "results"
    workload = read_json(root / "scripts/workload.json")
    work = {query["id"]: query for query in workload}
    runs = read_csv(result_dir / "query_runs.csv")
    node_runs = read_csv(result_dir / "node_runs.csv")
    environment = read_json(result_dir / "environment.json")
    require(len(workload) == len(work) == 20, "Expected 20 distinct SQL IDs")
    require(len({query["sql"] for query in workload}) == 20, "Duplicate SQL text")
    require(sum(query["source"] == "tpch" for query in workload) == 12,
            "Expected 12 TPC-H SQLs")
    require(sum(query["source"] == "synthetic" for query in workload) == 8,
            "Expected eight synthetic SQLs")
    require(environment["warmups"] == 1 and environment["measured_repeats"] == 3,
            "Expected one warmup plus three measurements")
    phases = ("baseline", "reanalyze_control", "extended")
    expected_keys = {
        (phase, query["id"], str(repeat))
        for phase in phases
        for query in workload
        if phase == "baseline" or query["source"] == "synthetic"
        for repeat in range(4)
    }
    actual_keys = {(row["phase"], row["query_id"], row["repeat"]) for row in runs}
    require(actual_keys == expected_keys and len(runs) == len(expected_keys) == 144,
            "Missing, duplicate, or unexpected query run")
    require(len({(row["phase"], row["query_id"]) for row in runs}) == 36,
            "Expected 36 query-phase combinations")
    warmup_count = sum(row["is_warmup"] == "True" for row in runs)
    require(warmup_count == 36, "Expected 36 warmup runs")

    nodes_by_run = collections.defaultdict(list)
    for row in node_runs:
        key = row["phase"], row["query_id"], row["repeat"]
        require(key in expected_keys, f"Unexpected node run: {key}")
        nodes_by_run[key].append(row)
    plans = {}
    for row in runs:
        key = row["phase"], row["query_id"], row["repeat"]
        query = work[row["query_id"]]
        require(row["title"] == query["title"] and row["group"] == query["group"]
                and row["source"] == query["source"], f"Metadata mismatch: {key}")
        require((row["is_warmup"] == "True") == (row["repeat"] == "0"),
                f"Warmup label mismatch: {key}")
        query_hash = hashlib.sha256(query["sql"].rstrip(";").encode()).hexdigest()
        require(row["sql_sha256"] == query_hash, f"SQL hash mismatch: {key}")
        plan_path = (result_dir / row["plan_file"]).resolve()
        require(plan_path.is_relative_to((result_dir / "plans").resolve()),
                f"Plan path escapes result directory: {key}")
        raw = read_json(plan_path)
        require(len(raw) == 1, f"Expected one EXPLAIN result: {key}")
        plan = raw[0]
        plan_root = plan["Plan"]
        plans[key] = plan_root
        require(plan_root["Actual Loops"] == 1, f"Root loops not one: {key}")
        require(plan_root["Node Type"] not in ("Aggregate", "Limit", "Gather", "Gather Merge"),
                f"Root cardinality not the intended complete SPJ output: {key}")
        require(plan["Settings"]["max_parallel_workers_per_gather"] == "0",
                f"Parallel query enabled: {key}")
        require(plan["Settings"]["work_mem"] == "64MB" and plan["Settings"]["jit"] == "off",
                f"Session setting mismatch: {key}")
        for csv_name, json_name in (("plan_rows", "Plan Rows"),
                                    ("actual_rows", "Actual Rows"),
                                    ("actual_loops", "Actual Loops"),
                                    ("total_cost", "Total Cost"),
                                    ("actual_total_time_ms", "Actual Total Time")):
            same_number(row[csv_name], plan_root[json_name], f"{key}/{csv_name}")
        require(row["root_node_type"] == plan_root["Node Type"], f"Root type mismatch: {key}")
        same_number(row["execution_time_ms"], plan["Execution Time"], f"{key}/execution time")
        same_number(row["planning_time_ms"], plan["Planning Time"], f"{key}/planning time")
        estimated, actual = plan_root["Plan Rows"], plan_root["Actual Rows"]
        if estimated > 0 and actual > 0:
            same_number(row["q_error"], max(estimated / actual, actual / estimated), f"{key}/Q")
        else:
            require(row["q_error"] == "", f"Strict Q should be blank for zero rows: {key}")
        safe_q = max(max(estimated, 1) / max(actual, 1), max(actual, 1) / max(estimated, 1))
        same_number(row["q_error_safe"], safe_q, f"{key}/safe Q")
        require((row["zero_actual"] == "True") == (actual == 0), f"Zero label mismatch: {key}")

        raw_nodes = dict(flatten(plan_root))
        csv_nodes = nodes_by_run[key]
        require(len(csv_nodes) == len(raw_nodes), f"Node count mismatch: {key}")
        require({node["node_path"] for node in csv_nodes} == set(raw_nodes),
                f"Node path mismatch: {key}")
        for item in csv_nodes:
            node_path = item["node_path"]
            node = raw_nodes[node_path]
            label = f"{key}/node {node_path}"
            require(item["parent_path"] == (node_path.rsplit(".", 1)[0] if "." in node_path else ""),
                    f"Parent path mismatch: {label}")
            require(item["node_type"] == node["Node Type"], f"Node type mismatch: {label}")
            require(item["relation"] == node.get("Relation Name", "") and
                    item["alias"] == node.get("Alias", ""), f"Node identity mismatch: {label}")
            require(item["plan_file"] == row["plan_file"], f"Plan linkage mismatch: {label}")
            require(item["is_warmup"] == row["is_warmup"], f"Node warmup mismatch: {label}")
            # The saved workload happens to contain Actual Rows for every node.
            require("Actual Rows" in node and "Actual Loops" in node,
                    f"Missing actual field must not be interpreted as zero: {label}")
            e, a, loops = node["Plan Rows"], node["Actual Rows"], node["Actual Loops"]
            same_number(item["plan_rows_per_loop"], e, f"{label}/estimated")
            same_number(item["actual_rows_per_loop"], a, f"{label}/actual")
            same_number(item["actual_loops"], loops, f"{label}/loops")
            same_number(item["actual_rows_total_approx"], a * loops, f"{label}/total rows")
            same_number(item["total_cost"], node["Total Cost"], f"{label}/cost")
            same_number(item["actual_total_time_ms_per_loop"], node["Actual Total Time"], f"{label}/time")
            require((item["executed"] == "True") == (loops > 0), f"Executed label mismatch: {label}")
            if e > 0 and a > 0 and loops > 0:
                same_number(item["q_error"], max(e / a, a / e), f"{label}/Q")
            else:
                require(item["q_error"] == "", f"Unexpected strict Q: {label}")
            if loops > 0:
                same_number(item["q_error_safe"], max(max(e, 1) / max(a, 1), max(a, 1) / max(e, 1)),
                            f"{label}/safe Q")
            else:
                require(item["q_error_safe"] == "", f"Unexecuted node Q not blank: {label}")

    require(len(list((result_dir / "plans").rglob("*.json"))) == len(runs),
            "Unexpected plan file count")
    expected_synthetic = {"S13": 3000, "S14": 3000, "S15": 30, "S16": 3000,
                          "S17": 0, "S18": 150000, "S19": 1515, "S20": 3000}
    for query_id in work:
        relevant = [row for row in runs if row["query_id"] == query_id]
        actuals = {int(row["actual_rows"]) for row in relevant}
        require(len(actuals) == 1, f"Actual cardinality changed across repetitions/phases: {query_id}")
        if query_id in expected_synthetic:
            require(actuals == {expected_synthetic[query_id]}, f"Synthetic truth mismatch: {query_id}")

    table_counts = {(row["schema"], row["table"]): int(row["rows"])
                    for row in read_csv(result_dir / "table_counts.csv")}
    expected_tables = {("tpch", "region"): 5, ("tpch", "nation"): 25,
                       ("tpch", "supplier"): 10000, ("tpch", "customer"): 150000,
                       ("tpch", "part"): 200000, ("tpch", "partsupp"): 800000,
                       ("tpch", "orders"): 1500000, ("tpch", "lineitem"): 6001215,
                       ("synthetic", "corr_independent"): 300000,
                       ("synthetic", "corr_dependent"): 300000,
                       ("synthetic", "corr_skewed"): 300000,
                       ("synthetic", "cross_customers"): 10000,
                       ("synthetic", "cross_orders"): 300000}
    require(table_counts == expected_tables, "SF=1/synthetic table count mismatch")
    snapshot_hashes = {phase: hashlib.sha256((result_dir / f"stats_{phase}.json").read_bytes()).hexdigest()
                       for phase in phases}
    require(len(set(snapshot_hashes.values())) == 1,
            "Single-column statistics changed; revise controlled-comparison conclusions")
    same_shapes = []
    for query_id in expected_synthetic:
        signatures = {shape(plans[(phase, query_id, str(repeat))])
                      for phase in phases for repeat in range(4)}
        if len(signatures) == 1:
            same_shapes.append(query_id)
    print(f"PASS: {len(work)} distinct SQLs; 36 query-phase combinations.")
    print(f"PASS: {len(runs)} raw plans = {warmup_count} warmups + {len(runs)-warmup_count} measurements.")
    print(f"PASS: {len(node_runs)} node records; SQL hashes, JSON/CSV values, Q-errors, and loops agree.")
    print(f"PASS: {sum(float(row['actual_loops']) > 1 for row in node_runs)} repeated node executions use per-loop Q-error.")
    print("PASS: all synthetic actual cardinalities agree with the generation rules.")
    print("PASS: single-column statistics snapshots have identical SHA-256:", next(iter(snapshot_hashes.values())))
    print("Synthetic queries with unchanged physical plan shapes:", ", ".join(same_shapes))
    for query_id in ("T09", "S16", "S17", "S18", "S19", "S20"):
        for phase in phases:
            values = [row for row in runs if row["query_id"] == query_id
                      and row["phase"] == phase and row["is_warmup"] == "False"]
            if values:
                median_ms = statistics.median(float(row["execution_time_ms"]) for row in values)
                print(f"{query_id} {phase}: E={values[0]['plan_rows']}, A={values[0]['actual_rows']}, "
                      f"Q={values[0]['q_error'] or 'undefined-at-zero'}, median={median_ms:.3f} ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="Experiment directory containing scripts/ and results/")
    arguments = parser.parse_args()
    main(arguments.root.resolve())
