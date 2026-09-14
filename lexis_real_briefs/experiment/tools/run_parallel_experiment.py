#!/usr/bin/env python3
"""Run fixture pairs concurrently, each in its own isolated runner process.

Each child invocation of run_experiment.py receives exactly one fixture. The
child makes a private SQLite copy and runs control then mutant back-to-back.
This parallelizes across pairs without sharing Django state or a database.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = ROOT / "lexis_real_briefs" / "experiment"
RUNNER = Path(__file__).with_name("run_experiment.py")


def fixture_ids(fixtures_dir: Path, selected: list[str] | None) -> list[str]:
    available = sorted(
        home.name for home in fixtures_dir.iterdir()
        if home.is_dir() and (home / "fixture.json").is_file()
    )
    if not selected:
        return available
    missing = sorted(set(selected) - set(available))
    if missing:
        raise SystemExit(f"Unknown fixture(s): {', '.join(missing)}")
    return [fixture_id for fixture_id in available if fixture_id in set(selected)]


def child_command(args, fixture_id: str, output: Path) -> list[str]:
    command = [
        sys.executable,
        str(RUNNER),
        "--output-dir",
        str(output),
        "--fixtures-dir",
        str(args.fixtures_dir),
        "--fixture",
        fixture_id,
        "--model",
        args.model,
        "--reasoning",
        args.reasoning,
    ]
    if args.live:
        command.append("--live")
    for option, value in (
        ("--attack-model", args.attack_model),
        ("--judge-model", args.judge_model),
        ("--base-model", args.base_model),
        ("--cell", args.cell),
    ):
        if value:
            command.extend([option, value])
    for check in args.check or []:
        command.extend(["--check", check])
    return command


def run_child(args, fixture_id: str, shards: Path) -> dict:
    output = shards / fixture_id
    log_path = shards / f"{fixture_id}.log"
    command = child_command(args, fixture_id, output)
    started = datetime.now(timezone.utc)
    with log_path.open("w", encoding="utf-8") as log:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    ended = datetime.now(timezone.utc)
    return {
        "fixture_id": fixture_id,
        "returncode": completed.returncode,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "elapsed_seconds": (ended - started).total_seconds(),
        "output_dir": str(output),
        "log": str(log_path),
        "command": command,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--fixtures-dir", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--attack-model")
    parser.add_argument("--judge-model")
    parser.add_argument("--base-model")
    parser.add_argument("--cell")
    parser.add_argument("--reasoning", default="medium")
    parser.add_argument("--fixture", action="append")
    parser.add_argument("--check", action="append")
    args = parser.parse_args()

    args.fixtures_dir = args.fixtures_dir.resolve()
    output = args.output_dir.resolve()
    results_root = (EXPERIMENT / "results").resolve()
    if results_root not in output.parents:
        parser.error("Output directory must be inside lexis_real_briefs/experiment/results")
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    if output.exists():
        parser.error(f"Refusing to overwrite existing output: {output}")

    fixtures = fixture_ids(args.fixtures_dir, args.fixture)
    if not fixtures:
        parser.error("No matching fixtures")
    output.mkdir(mode=0o700, parents=True)
    shards = output / "shards"
    shards.mkdir()
    workers = min(args.jobs, len(fixtures))
    print(f"Running {len(fixtures)} fixture pairs with {workers} isolated workers", flush=True)

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(run_child, args, fixture_id, shards): fixture_id
            for fixture_id in fixtures
        }
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            state = "complete" if row["returncode"] == 0 else "FAILED"
            print(
                f"[{len(rows)}/{len(fixtures)}] {row['fixture_id']} {state} "
                f"({row['elapsed_seconds']:.1f}s; {row['log']})",
                flush=True,
            )

    rows.sort(key=lambda row: row["fixture_id"])
    aggregate = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "workers": workers,
        "fixtures": fixtures,
        "shards": rows,
    }
    (output / "parallel-report.json").write_text(
        json.dumps(aggregate, indent=2) + "\n", encoding="utf-8"
    )
    failed = [row for row in rows if row["returncode"] != 0]
    if failed:
        print(
            "Failed shards: " + ", ".join(row["fixture_id"] for row in failed),
            flush=True,
        )
        return 1
    print(f"Saved parallel run to {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
