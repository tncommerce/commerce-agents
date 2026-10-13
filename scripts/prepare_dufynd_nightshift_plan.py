"""Prepare a disabled, hash-bound offline DUFYND queue. Never install or activate it."""

from __future__ import annotations

import argparse
import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.dufynd_zero_cost_nightshift import (
    MAX_FILE_BYTES,
    REPOSITORY,
    RUNNER_SHA,
    Gate,
    canonical,
    checkout_identity,
    read_input,
    timestamp,
    validate_plan,
)

SOURCE = "docs/dufynd-nightshift-source-intake-20261012.json"
CATALOG = (
    "examples/retail/data/dufynd_catalog_expansion_next10.json",
    "examples/retail/data/catalog.json",
    "examples/retail/data/scentai_catalog_staging.json",
)
QA = "examples/retail/data/scentai_catalog_batch3_commerce_qa.json"


def prepare(root, plan_id, starts_at, ends_at):
    start = datetime.fromtimestamp(timestamp(starts_at), UTC)

    def reference(path):
        # read_input supplies the same size/path/strict-JSON gates as execution.
        target = root
        for part in Path(path).parts:
            target /= part
            if target.is_symlink():
                raise Gate("input_symlink_denied")
        with target.open("rb") as handle:
            raw = handle.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise Gate("input_too_large")
        ref = {"path": path, "sha256": hashlib.sha256(raw).hexdigest()}
        read_input(root, ref)
        return ref

    tasks = []
    for offset, (tid, action, paths) in enumerate(
        (
            ("a_awin_original_report", "owner_gate", ()),
            ("b_manufacturer_packet_structure", "source_intake", (SOURCE,)),
            ("c_catalog_preintake_audit", "catalog_wave_audit", CATALOG),
            ("d_archived_qa_json_integrity", "json_integrity", (QA,)),
        )
    ):
        task = {
            "task_id": tid,
            "action": action,
            "due_at": (start + timedelta(seconds=offset)).isoformat(),
            "max_attempts": 2,
            "inputs": [reference(path) for path in paths],
            "depends_on": [],
        }
        if action == "owner_gate":
            task.update(hold_reason="source_report_missing", max_attempts=1)
        tasks.append(task)
    return validate_plan(
        {
            "schema_version": 1,
            "repository": REPOSITORY,
            "plan_id": plan_id,
            "checkout_sha": checkout_identity(root),
            "runner_sha256": RUNNER_SHA,
            "enabled": False,
            "production_activation": False,
            "max_external_cost_eur": 0,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "max_attempts": 6,
            "max_tasks_per_tick": 3,
            "tasks": tasks,
        }
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--starts-at", required=True)
    parser.add_argument("--ends-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        plan = prepare(args.root.resolve(), args.plan_id, args.starts_at, args.ends_at)
        # Never overwrite an existing approved plan or follow a target symlink.
        fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(canonical(plan) + "\n")
        print(canonical({"status": "PREPARED_DISABLED", "tasks": len(plan["tasks"])}))
        return 0
    except (Gate, OSError):
        print(canonical({"status": "PLAN_PREPARATION_REFUSED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
