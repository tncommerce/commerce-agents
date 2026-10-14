"""Fixed pure-function child. No credentials, sockets, providers or subprocesses."""

from __future__ import annotations

import json
import resource
import sys
from datetime import UTC, datetime
from pathlib import Path


def deny_external(event, args):
    if event in {
        "socket.__new__",
        "socket.connect",
        "subprocess.Popen",
        "os.system",
        "os.exec",
        "os.fork",
    }:
        raise PermissionError("zero_cost_external_execution_denied")


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    sys.dont_write_bytecode = True
    sys.addaudithook(deny_external)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.dufynd_nightshift_value_v2 import prepare

    raw = sys.stdin.buffer.read(250001)
    if len(raw) > 250000:
        raise ValueError("bounded_input_required")
    packet = json.loads(raw)
    if set(packet) != {"handler", "sources", "pins"} or packet["handler"] not in {
        "first_money_action/2",
        "editorial_handoff/2",
    }:
        raise ValueError("unknown_handler")
    plan = prepare(packet["sources"], packet["pins"], now=datetime.now(UTC))
    result = next(i["result"] for i in plan["items"] if i["handler"] == packet["handler"])
    output = json.dumps(result, ensure_ascii=False, allow_nan=False)
    if len(output.encode()) > 200000:
        raise ValueError("bounded_output_required")
    print(output)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never echo source data, provider error strings or secrets into logs.
        print("value_worker_input_or_execution_hold", file=sys.stderr)
        raise SystemExit(2) from None
