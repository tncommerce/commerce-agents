# DUFYND OpenRouter Read-Only Worker

Status: experimental_internal
Brand: DUFYND
Operator: TNCommerce

## Purpose

This worker is a low-cost analysis lane for DUFYND and future Jarvis routing.
It is deliberately separate from the Claude Agent SDK runtime.

The default model is:

```text
z-ai/glm-5.3-flash:free
```

The worker is read-only. It has no publishing, spending, merge, outbound-message,
contract, or production-write tools.

## Safety defaults

- Paid OpenRouter models are blocked by default.
- Only model slugs ending in `:free` run without an explicit paid-model gate.
- Internal DUFYND operating context is blocked by default.
- Secrets must never be placed in prompts.
- The first validation phase should use public repository content or synthetic
  prompts only.
- The existing Claude Jarvis runtime remains unchanged.

Free endpoints can have provider-specific logging or training terms. Review the
selected provider policy before enabling internal context.

## Local setup

Create an OpenRouter API key in the OpenRouter dashboard. Do not paste the key
into chat, GitHub, source code, or a committed settings file.

In PowerShell:

```powershell
cd $HOME\TNCommerce\commerce-agents
$env:OPENROUTER_API_KEY = Read-Host "OpenRouter API key"
python -m scripts.dufynd_openrouter_worker --readiness
```

The readiness output should report:

```text
"free_model": true
"openrouter_key_configured": true
"ready_for_read_only_request": true
```

## First free request

Use a non-sensitive prompt first:

```powershell
cd $HOME\TNCommerce\commerce-agents
python -m scripts.dufynd_openrouter_worker --once "Return exactly: DUFYND OpenRouter worker OK"
```

The footer prints the model and token usage returned by OpenRouter.

## Selecting another free model

```powershell
cd $HOME\TNCommerce\commerce-agents
$env:DUFYND_OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
python -m scripts.dufynd_openrouter_worker --readiness
```

Keep the `:free` suffix during the experimental phase.

## Internal operating context

Do not enable this during the first connectivity test.

When the provider data policy has been reviewed and the operator explicitly
accepts it, internal context can be enabled for a single local session:

```powershell
cd $HOME\TNCommerce\commerce-agents
$env:DUFYND_OPENROUTER_ALLOW_INTERNAL_CONTEXT = "1"
python -m scripts.dufynd_openrouter_worker --with-operating-context "Summarize the current DUFYND operating priorities without making changes."
```

This mode reads the current Jarvis operating context but still exposes no
write tools.

## Paid models

Paid OpenRouter models remain blocked unless the operator explicitly enables:

```powershell
$env:DUFYND_OPENROUTER_ALLOW_PAID = "1"
```

Enabling that flag does not itself buy credits or change the existing Jarvis
budget window. It only removes this worker's local `:free` guard.

## Next integration gate

Only after the free worker proves useful should Jarvis gain a task router.
The intended routing split is:

- high-token, low-risk analysis -> OpenRouter read-only worker
- production-affecting or higher-risk reasoning -> existing premium runtime
- any publishing, spending, important outbound, contracts, or production merge
  -> human approval remains mandatory
