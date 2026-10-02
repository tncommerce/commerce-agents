"""Validate the certified task packet and expose only its fenced worker tools.

The database selects and hashes the immutable packet. This worker has no command,
chat-history or provider interpreter. Runtime fence/checkpoint come from the ledger.
"""

from __future__ import annotations

from typing import Any

CAPABILITIES = frozenset({"supabase.execution_state"})
TOOLS = frozenset({"checkpoint_dufynd_execution", "finish_dufynd_execution"})
FORBIDDEN = frozenset(
    {
        "gmail.send",
        "social.publish",
        "budget.spend",
        "main.merge",
        "commerce.activate",
        "shell.execute",
    }
)


def validate_packet(execution: dict[str, Any]) -> dict[str, Any]:
    packet = execution.get("task_packet")
    if (
        not isinstance(packet, dict)
        or type(packet.get("packet_version")) is not int
        or packet.get("packet_version") != 1
    ):
        raise ValueError("uncertified_task_packet")
    if (
        packet.get("handler_id") != "durability_probe"
        or packet.get("handler_version") != "1"
        or execution.get("handler_id") != packet["handler_id"]
        or execution.get("handler_version") != packet["handler_version"]
        or packet.get("task_id") != execution["task_id"]
        or packet.get("execution_id") != execution["execution_id"]
        or packet.get("explicit_scope") != execution.get("scope")
        or packet.get("allowed_resources") != execution.get("resources")
        or packet.get("payload") != execution["payload"]
        or packet.get("required_capabilities") != sorted(CAPABILITIES)
        or set(packet.get("allowed_tools", [])) != TOOLS
        or not FORBIDDEN.issubset(packet.get("forbidden_actions", []))
        or TOOLS.intersection(packet.get("forbidden_actions", []))
        or CAPABILITIES.intersection(packet.get("forbidden_actions", []))
        or packet.get("verification_contract") != {"kind": "arithmetic_checkpoint", "version": 1}
        or not execution.get("packet_hash")
    ):
        raise ValueError("uncertified_task_packet_contract")
    return packet


class PacketTools:
    """Task-bound allowlist; neither resources nor fencing can be caller-overridden."""

    def __init__(self, bridge, execution):
        self.packet = validate_packet(execution)
        self._bridge = bridge
        self._identity = {
            "p_execution_id": execution["execution_id"],
            "p_token": execution["lease_token"],
            "p_worker_id": execution["worker_id"],
        }

    def call(self, name: str, **arguments):
        if name not in TOOLS or name in self.packet["forbidden_actions"]:
            raise ValueError("tool_not_in_packet")
        allowed = {"p_step"} if name == "checkpoint_dufynd_execution" else set()
        if set(arguments) - allowed:
            raise ValueError("packet_tool_arguments_outside_scope")
        return self._bridge._rpc(name, self._identity | arguments)
