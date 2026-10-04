"""Count-only acceptance: no database adapter, reservations, task claims or generation."""

import json
import os
from pathlib import Path

from scripts.dufynd_anthropic_counted import CountedClient, input_body
from scripts.dufynd_token_context import TARGET_INPUT, fit_context
from scripts.dufynd_worker_evidence import encode


class CountOnlyClient(CountedClient):
    def _post(self, path, payload):
        if path != "/count_tokens":
            raise RuntimeError("paid_messages_endpoint_forbidden")
        return super()._post(path, payload)

    def execute(self, *args, **kwargs):
        raise RuntimeError("paid_execution_forbidden")


def main():
    client = CountOnlyClient(os.environ.get("ANTHROPIC_API_KEY", ""))
    tasks = json.loads(Path("tests/fixtures/dufynd_pre_canary_real_tasks.json").read_text())
    out = Path("jarvis-context-count-report")
    out.mkdir(exist_ok=True)
    reports = []
    for task in tasks:
        trace = []
        try:
            packet, prompt, count = fit_context(
                task, head=os.environ.get("GITHUB_SHA"), client=client, trace=trace
            )
            name = task["domain"]
            out.joinpath(name + "-context.json").write_bytes(encode(packet))
            out.joinpath(name + "-count-input.json").write_bytes(encode(input_body(prompt)))
            reports.append(
                {
                    "task_id": task["task_id"],
                    "accepted": True,
                    "official_input_tokens": count,
                    "trace": trace,
                    "packet_sha256": packet["packet_sha256"],
                }
            )
        except Exception as error:
            reports.append(
                {
                    "task_id": task["task_id"],
                    "accepted": False,
                    "reason": str(error)
                    if type(error).__name__ == "BudgetGate"
                    else type(error).__name__,
                    "trace": trace,
                }
            )
    report = {
        "head": os.environ.get("GITHUB_SHA"),
        "target_input": TARGET_INPUT,
        "paid_calls": 0,
        "reservations": 0,
        "task_claims": 0,
        "results": reports,
    }
    out.joinpath("official-count-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    return 0 if all(r["accepted"] for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
