from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from typing import Any

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "z-ai/glm-5.3-flash:free"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT_S = 180.0

SYSTEM_PROMPT = """You are a read-only analysis worker for DUFYND, operated by TNCommerce.

DUFYND is the current public brand. SCENTAI is historical/legacy only.

You may analyze, summarize, compare, review, classify, and propose next steps.
You must not claim that you published content, spent money, bought credits,
changed production, merged code, sent outbound messages, signed contracts, or
modified the DUFYND knowledge base. You have no tools for those actions.

Treat supplied context as evidence. Separate observed facts from hypotheses.
Do not invent missing data. Prefer concise, actionable outputs.
"""

FREE_ENDPOINT_NOTICE = (
    "Free OpenRouter endpoints can use provider-specific data handling. "
    "Do not send secrets, personal data, or confidential business material."
)


def _env_flag(name: str) -> bool:
    return os.getenv(name) == "1"


def selected_model(value: str | None = None) -> str:
    return value or os.getenv("DUFYND_OPENROUTER_MODEL") or DEFAULT_MODEL


def runtime_readiness(model: str | None = None) -> dict[str, Any]:
    resolved_model = selected_model(model)
    key_configured = bool(os.getenv("OPENROUTER_API_KEY"))
    free_model = resolved_model.endswith(":free")
    paid_allowed = _env_flag("DUFYND_OPENROUTER_ALLOW_PAID")
    return {
        "model": resolved_model,
        "free_model": free_model,
        "openrouter_key_configured": key_configured,
        "paid_models_allowed": paid_allowed,
        "internal_context_allowed": _env_flag(
            "DUFYND_OPENROUTER_ALLOW_INTERNAL_CONTEXT"
        ),
        "ready_for_read_only_request": key_configured
        and (free_model or paid_allowed),
        "notice": FREE_ENDPOINT_NOTICE,
    }


def _require_model(model: str) -> str:
    if model.endswith(":free"):
        return model
    if not _env_flag("DUFYND_OPENROUTER_ALLOW_PAID"):
        raise RuntimeError(
            "Paid OpenRouter models are disabled. Use a :free model or set "
            "DUFYND_OPENROUTER_ALLOW_PAID=1 after explicit operator approval."
        )
    return model


def _require_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is required.")
    return key


def _require_internal_context_allowed() -> None:
    if not _env_flag("DUFYND_OPENROUTER_ALLOW_INTERNAL_CONTEXT"):
        raise RuntimeError(
            "Internal DUFYND context is disabled for OpenRouter free workers. "
            "Set DUFYND_OPENROUTER_ALLOW_INTERNAL_CONTEXT=1 only after reviewing "
            "the selected provider's data policy."
        )


def build_payload(
    prompt: str,
    *,
    model: str,
    operating_context: dict[str, Any] | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    user_text = prompt
    if operating_context is not None:
        user_text = (
            prompt
            + "\n\nDUFYND operating context:\n"
            + json.dumps(operating_context, ensure_ascii=False, default=str)
        )
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": max_tokens,
    }


def _extract_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("OpenRouter returned no choices.")
    content = (choices[0].get("message") or {}).get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n".join(part.strip() for part in parts if part.strip())
    raise RuntimeError("OpenRouter returned an unsupported message format.")


def call_openrouter(
    prompt: str,
    *,
    model: str | None = None,
    operating_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_model = _require_model(selected_model(model))
    key = _require_key()
    raw_max_tokens = os.getenv(
        "DUFYND_OPENROUTER_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)
    )
    raw_timeout = os.getenv(
        "DUFYND_OPENROUTER_TIMEOUT_S", str(DEFAULT_TIMEOUT_S)
    )
    try:
        max_tokens = max(1, min(int(raw_max_tokens), 65_536))
    except ValueError as error:
        raise RuntimeError(
            "DUFYND_OPENROUTER_MAX_TOKENS must be an integer."
        ) from error
    try:
        timeout_s = max(1.0, min(float(raw_timeout), 600.0))
    except ValueError as error:
        raise RuntimeError(
            "DUFYND_OPENROUTER_TIMEOUT_S must be numeric."
        ) from error

    payload = build_payload(
        prompt,
        model=resolved_model,
        operating_context=operating_context,
        max_tokens=max_tokens,
    )
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://dufynd.de",
            "X-Title": "DUFYND Jarvis Read-Only Worker",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenRouter HTTP {error.code}: {detail[:1200]}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"OpenRouter request failed: {error}") from error

    usage = response_payload.get("usage") or {}
    return {
        "text": _extract_text(response_payload),
        "model": response_payload.get("model") or resolved_model,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "cost": usage.get("cost"),
    }


def _load_operating_context() -> dict[str, Any]:
    _require_internal_context_allowed()
    from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

    return DufyndJarvisBridge().load_context()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only DUFYND worker backed by OpenRouter."
    )
    parser.add_argument(
        "--model",
        help=f"OpenRouter model slug. Default: {DEFAULT_MODEL}",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--readiness",
        action="store_true",
        help="report configuration without making a model request",
    )
    group.add_argument(
        "--once",
        metavar="PROMPT",
        help="run one read-only model request without DUFYND internal context",
    )
    group.add_argument(
        "--with-operating-context",
        metavar="PROMPT",
        help="run one read-only request with DUFYND operating context",
    )
    args = parser.parse_args()

    if args.readiness:
        print(
            json.dumps(
                runtime_readiness(args.model),
                ensure_ascii=False,
            )
        )
        return 0

    context = None
    prompt = args.once
    if args.with_operating_context is not None:
        context = _load_operating_context()
        prompt = args.with_operating_context

    result = call_openrouter(
        str(prompt),
        model=args.model,
        operating_context=context,
    )
    if result["text"]:
        print(result["text"])
    print(
        "[OpenRouter worker] "
        f"model={result['model']} "
        f"prompt_tokens={result['prompt_tokens']} "
        f"completion_tokens={result['completion_tokens']} "
        f"cost={result['cost']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
