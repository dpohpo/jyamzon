#!/usr/bin/env python3
"""Create deterministic candidate shards for slower detail-page retry work."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DATA_DIR = Path("data/amazon_3c/filtered_30_opportunities")
SHARD_DIR = DATA_DIR / "retry_shards"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards", type=int, default=4)
    parser.add_argument("--max-candidates", type=int, default=1200)
    parser.add_argument("--output-dir", type=Path, default=SHARD_DIR)
    parser.add_argument("--max-attempts-per-shard", type=int, default=350)
    args = parser.parse_args()

    candidates = load_json(DATA_DIR / "candidate_asins.json", [])
    selected = load_json(DATA_DIR / "selected_30.json", [])
    accepted = load_json(DATA_DIR / "accepted_pool.json", [])
    seen = {row.get("asin") for row in selected + accepted if row.get("asin")}

    remaining = []
    for candidate in candidates:
        asin = candidate.get("asin")
        if not asin or asin in seen:
            continue
        remaining.append(candidate)
        if len(remaining) >= args.max_candidates:
            break

    input_dir = args.output_dir / "inputs"
    result_dir = args.output_dir / "results"
    input_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)

    commands = []
    for shard_idx in range(args.shards):
        rows = remaining[shard_idx :: args.shards]
        shard_input = input_dir / f"shard_{shard_idx:02d}.json"
        shard_output = result_dir / f"shard_{shard_idx:02d}.json"
        write_json(shard_input, rows)
        commands.append(
            "python scripts/run_detail_retry_shard.py "
            f"--input {shard_input} --output {shard_output} --max-attempts {args.max_attempts_per_shard}"
        )

    command_file = args.output_dir / "commands.txt"
    command_file.write_text("\n".join(commands) + "\n", encoding="utf-8")
    manifest = {
        "candidate_count": len(candidates),
        "excluded_already_seen": len(seen),
        "planned_candidates": len(remaining),
        "shards": args.shards,
        "input_dir": str(input_dir),
        "result_dir": str(result_dir),
        "commands_file": str(command_file),
    }
    write_json(args.output_dir / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
