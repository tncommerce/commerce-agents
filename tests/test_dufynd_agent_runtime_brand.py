"""Keep the runtime shopping assistant customer-facing brand on DUFYND."""

from pathlib import Path

AGENT_CONFIG = Path("examples/retail/api/agent_config.py")


def test_runtime_agent_uses_dufynd_brand_and_assistant_name() -> None:
    source = AGENT_CONFIG.read_text(encoding="utf-8")

    assert 'brand_name="DUFYND"' in source
    assert 'assistant_name="DUFYND Advisor"' in source
    assert 'brand_name="SCENTAI"' not in source
    assert 'assistant_name="SCENTAI Advisor"' not in source


def test_customer_facing_runtime_rules_do_not_name_scentai() -> None:
    source = AGENT_CONFIG.read_text(encoding="utf-8")
    runtime_rules = source.split("domain_search_notes=(", 1)[1].split("        ),", 1)[0]

    assert "SCENTAI" not in runtime_rules
