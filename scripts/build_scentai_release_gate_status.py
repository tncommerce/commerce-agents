.py>>>
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_MAPPING = DATA_DIR / "scentai_merchant_mapping_work_queue.json"
DEFAULT_AFFILIATE = DATA_DIR / "scentai_affiliate_activation_status.json"
DEFAULT_IMAGES = DATA_DIR / "scentai_image_approval_work_queue.json"
DEFAULT_RELEASE = DATA_DIR / "scentai_release_01_gate_status.json"
DEFAULT_FEED = DATA_DIR / "scentai_release_01_feed_activation_queue.json"
DEFAULT_OUTPUT = DATA_DIR / "scentai_jarvis_operations_status.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def source_fingerprint(*payloads: object) -> str:
    digest = hashlib.sha256()
    for payload in payloads:
        digest.update(canonical_bytes(payload))
    return digest.hexdigest()


def build_operations_status(
    mapping: dict,
    affiliate: dict,
    images: dict,
    release: dict,
    feed: dict,
    *,
    generated_at: str,
) -> dict[str, Any]:
    mapping_summary = mapping.get("summary", {})
    affiliate_summary = affiliate.get("summary", {})
    image_summary = images.get("summary", {})
    release_summary = release.ge
…[84824 chars truncated — re-run with head/grep/tail for full output]…
get("description", "")
    return mcp_tools, custom


def backticked_after_preamble(line: str) -> set[str]:
    return set(re.findall(r"`([a-z_]+)`", line.split("):", 1)[-1]))


def readme_line(path: Path, marker: str) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if marker in line:
            return line
    problem(f"{path.relative_to(REPO_ROOT)}: no '{marker}' line found")
    return ""


def check_managed_readme_tool_lists() -> None:
    """Each managed-agents README lists the deployed tools by hand; its count row and
    two tool bullets, and the server README's table, must match agent.yaml."""
    print("managed-agents READMEs vs agent.yaml")
    for role in ROLES:
        mcp_tools, custom = manifest_tools(role.agent_dir / "agent.yaml")
        before = len(PROBLEMS)
        agent_readme = role.managed / "README.md"
        parent = agent_readme.read_text(encoding="utf-8")
        counts = re.search(rf"(\d+) {role.server_label}, (\d+) presentation tools", parent)
        if counts is None:
            problem(
                f"{role.tree} managed README: no '<N> {role.server_label}, <N> presentation tools' row"
            )
        elif (int(counts.group(1)), int(counts.group(2))) != (len(mcp_tools), len(custom)):
            problem(
                f"{role.tree} managed README counts disagree with agent.yaml ({len(mcp_tools)} / {len(custom)})"
            )
        marker = f"**{role.server_label.split()[0].capitalize()} tools**"
        if (listed := backticked_after_preamble(readme_line(agent_readme, marker))) != mcp_tools:
            problem(
                f"{agent_readme.relative_to(REPO_ROOT)}: {role.server_label} list != agent.yaml "
                f"(missing {sorted(mcp_tools - listed)}, extra {sorted(listed - mcp_tools)})"
            )
        listed = backticked_after_preamble(readme_line(agent_readme, "**Presentation tools**"))
        if listed != set(custom):
            problem(
                f"{agent_readme.relative_to(REPO_ROOT)}: presentation list != agent.yaml "
                f"(missing {sorted(set(custom) - listed)}, extra {sorted(listed - set(custom))})"
            )
        server_readme = (role.managed / role.server_dir / "README.md").read_text(encoding="utf-8")
        rows = set(re.findall(r"^\| `([a-z_]+)` \|", server_readme, re.MULTILINE))
        if rows != mcp_tools:
            problem(
                f"{role.tree} {role.server_dir}/README.md tool table != agent.yaml "
                f"(missing {sorted(mcp_tools - rows)}, extra {sorted(rows - mcp_tools)})"
            )
        if len(PROBLEMS) == before:
            ok(f"{role.tree}: README counts, tool lists, and server table match agent.yaml")


def check_managed_custom_tool_descriptions() -> None:
    """The manifests' custom tool descriptions are the registries', whitespace aside."""
    print("managed-agents custom tool descriptions vs the registries")
    for role in ROLES:
        registry = role.registry_descriptions()
        _, custom = manifest_tools(role.agent_dir / "agent.yaml")
        before = len(PROBLEMS)
        for name, description in custom.items():
            if name not in registry:
                problem(f"{role.tree} agent.yaml: custom tool {name} has no registry contract")
            elif normalize_ws(description) != normalize_ws(registry[name]):
                problem(f"{role.tree} agent.yaml: {name} description drifted from the registry")
        if len(PROBLEMS) == before:
            ok(f"{role.tree}: {len(custom)} custom tool descriptions match the registry")


def check_scentai_jarvis_operations_status() -> None:
    """Keep the committed Jarvis control-plane snapshot aligned with source state."""
    print("SCENTAI Jarvis operations status")
    try:
        from scripts.validate_scentai_jarvis_operations_status import (
            validate_operations_status,
        )

        data = REPO_ROOT / "examples" / "retail" / "data"
        report = validate_operations_status(
            load_json(data / "scentai_jarvis_operations_status.json"),
            load_json(data / "scentai_merchant_mapping_work_queue.json"),
            load_json(data / "scentai_affiliate_activation_status.json"),
            load_json(data / "scentai_image_approval_work_queue.json"),
            load_json(data / "scentai_release_01_gate_status.json"),
            load_json(data / "scentai_release_01_feed_activation_queue.json"),
        )
    except Exception as error:
        problem(f"SCENTAI Jarvis operations parity check failed: {error}")
        return

    if not report["valid"]:
        for issue in report["issues"]:
            problem(f"SCENTAI Jarvis operations status: {issue}")
        return

    ok("SCENTAI Jarvis operations snapshot matches source state")


def check_scentai_jarvis_state_graph() -> None:
    """Ensure every committed Jarvis derived view matches source-of-truth data."""
    print("SCENTAI Jarvis state graph")
    try:
        from scripts.validate_scentai_jarvis_state_graph import (
            validate_repo_state_graph,
        )

        report = validate_repo_state_graph()
    except Exception as error:
        problem(f"SCENTAI Jarvis state graph check failed: {error}")
        return

    if not report["valid"]:
        for issue in report["issues"]:
            problem(f"SCENTAI Jarvis state graph: {issue}")
        return

    ok("SCENTAI Jarvis derived state graph matches source-of-truth")


def check_scentai_pilot_batch_contract() -> None:
    """Keep Pilot Batch 01 IDs, timings, links and production jobs aligned."""
    print("SCENTAI pilot production contract")
    try:
        from scripts.validate_scentai_pilot_batch_contract import (
            validate_contract,
        )

        data = REPO_ROOT / "examples" / "retail" / "data"
        report = validate_contract(
            load_json(data / "scentai_pilot_batch_01.json"),
            load_json(data / "scentai_pilot_batch_01_production_jobs.json"),
            load_json(data / "scentai_pilot_batch_01_subtitles.json"),
            load_json(data / "scentai_pilot_batch_01_links.json"),
            load_json(data / "scentai_pilot_batch_01_social_copy.json"),
        )
    except Exception as error:
        problem(f"SCENTAI pilot production contract failed: {error}")
        return

    if not report["valid"]:
        for issue in report["issues"]:
            problem(f"SCENTAI pilot contract: {issue}")
        return

    ok(
        "SCENTAI Pilot Batch 01 contract is internally consistent "
        f"({report['summary']['pilots']} pilots, "
        f"{report['summary']['tracked_links']} tracked links)"
    )


CHECKS = (
    check_skills,
    check_storefront_fixtures,
    check_ticketing_fixtures,
    check_merchant_fixtures,
    check_verification_wiring,
    check_package_versions,
    check_manifests,
    check_managed_system_prompts,
    check_managed_readme_tool_lists,
    check_managed_custom_tool_descriptions,
    check_scentai_jarvis_operations_status,
    check_scentai_jarvis_state_graph,
    check_scentai_pilot_batch_contract,
)


def main() -> int:
    for check in CHECKS:
        check()
        print()
    if PROBLEMS:
        print(f"check.py: {len(PROBLEMS)} problem(s)")
        return 1
    print("check.py: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
