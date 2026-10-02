# Supervisor V2 Phase 2A.2 — bounded request preparation and certification audit

## Result and authorization boundary

The direct Messages HTTP framing, strict immutable request, price calculation,
usage parser, and existing Phase-2A reservation/dispatch/settlement integration
are technically prepared and verified with mocks. **No real provider is certified.**
Real Anthropic and OpenRouter candidates remain `BOUND_UNKNOWN`; this is a
certification blocker, not authorization to substitute estimates or a margin.
The old SDK's unconditional execution block remains unchanged. No real call,
price lookup, token-count API call, owner approval, live budget increase or budget
activation was performed. The simulated canary does not simulate owner approval.

A real paid canary requires both a new explicit owner budget and a completed
real-provider certification. Asking for budget now would not resolve the missing
technical guarantee. The operator must not mistake the test fixture for a real
provider contract or claim that paid Jarvis is executable after this phase.

## Live audit at start

GitHub `scentai-mvp` was `d47d08fd4a1fbcd55fe86c689d132f4952b6c0cd`,
PR610/611 merged, post-merge CI green, Render backend on that exact commit.
Supabase: old pilot cap $2.50; 19 runs; precise stored sum
$2.504685399999999955, remaining zero. No enabled reservation window, enabled
provider contract or durable test reservation. Autonomous two-minute watchdog
persists reservation reconciliation; three paid tasks parked, no false human gate.

### Existing execution paths

| Item | Observed implementation | Certification consequence |
| --- | --- | --- |
| Model selection | `DUFYND_JARVIS_MODEL` is required; Actions supplies repository variable. Budget row pins `claude-sonnet-5`; runtime checks equality. Current repository variable value was not observable through available read capabilities. | No assumed effective variable/default. Any enabled path must match an approved exact model. |
| Event/task input | `event_prompt`, safe/branch task prompts serialize event/task JSON; system prompt and MCP tool results join the SDK conversation. Built-in Read/Grep/Glob and selected web tools may add data. | No exact whole-conversation pre-dispatch token proof. Paging is not a total request/token cap. The 4,000-character audit-summary slice does not limit model input. |
| SDK output | `max_turns` and `max_budget_usd`; no explicit per-API-call `max_tokens` in the three option builders. SDK's installed type documentation says it stops after budget is exceeded. | Post-call threshold cannot certify next call. |
| Tool/reasoning use | SDK controls tool loops and implicit context. Safe worker allows WebSearch/WebFetch; branch worker Read/Grep/Glob/Write/Edit; MCP schemas/results enter context. | Additional calls and server-side charges cannot be ignored. No fixed price/max-next-call proof in this SDK path. |
| Prices | SDK result supplies `total_cost_usd` after execution; runtime approval and SDK allowance use floats and an 80% margin. Existing cost ledger is now exact numeric. | Actual cost is audit evidence, not a pre-dispatch upper bound. |
| Retries | Installed Anthropic client defaults `max_retries=2`; Agent SDK is a separate CLI transport. | New path uses neither client nor CLI retry behavior. SDK internal call behavior is not inferred from Messages client defaults. |

Audit sources: `scripts/dufynd_jarvis_runtime.py`, installed
`claude_agent_sdk/types.py`, installed `anthropic/types/message_create_params.py`,
`anthropic.Anthropic` signature, manual workflow environment bindings and the live
budget row. No secret values were read or printed.

## Provider documentation and exact blockers

Documentation reviewed 2026-10-02:

1. [Anthropic token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting)
   explicitly describes counts as estimates. Actual input can differ, and there
   is no documented numerical maximum error. System-added optimization tokens are
   described as non-billed, but that does not make the estimate an exact bound.
2. [Thinking cost control](https://platform.claude.com/docs/en/build-with-claude/thinking-steering-and-cost)
   guarantees `max_tokens` caps thinking plus visible text **per request**. Effort
   is soft guidance. Each request in a tool loop has its own limit.
3. [Sonnet 5](https://platform.claude.com/docs/en/models/sonnet-5/overview)
   documents model ID `claude-sonnet-5`, 1M context, 128K output, $2/MTok input,
   $10/MTok output. These observed published tariffs are versioned in the catalog,
   but are not a provider-accepted request price ceiling.
4. [Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
   lists cache writes/reads, server tools, region multipliers, fast mode and
   managed-agent runtime classes. The prepared direct path prohibits tools,
   cache control, files/images, managed sessions, batches, speed and priority;
   pins global geography and standard tier. Thinking is disabled, but the output
   accounting still treats hidden reasoning as part of billed total output.
5. [Context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows)
   describes context exhaustion behavior. A model's advertised global context
   capacity does not prove a specific 4,096-token request limit, supply an exact
   pre-dispatch count, or bind the unit tariff. Reserving a full model context is
   therefore not used to bypass the missing request-specific proof.
6. [OpenRouter routing](https://openrouter.ai/docs/guides/routing/provider-selection)
   supports request `provider.max_price` filters for prompt/completion/request
   tariffs, and fails when no acceptable price is available. This is a promising
   alternative to a published-rate-only contract. However its documented
   [max_tokens](https://openrouter.ai/docs/api-reference/parameters) covers
   reasoning plus visible output on **most** providers, not all. Automatic
   provider transformations/caching and an exact route-specific input tokenizer
   are not certified here. The Claude route remains closed. No OpenRouter
   account connection or request was made.

The current real blockers are: exact/upper-bounded model-specific input counting,
server-enforced applicable unit-price ceiling, and a complete certified accounting
of the selected route's billing classes. No undocumented UTF-8/tiktoken heuristic,
percentage buffer, tokenizer from another model or optimistic cache discount is
accepted as proof.

## Request/cost contract and transport

`config/dufynd_provider_contracts_v1.json` stores version, review time, expiry,
provider/model, token limits, prices, proof flags, blockers and source URLs.
`load_contract` produces an immutable certificate plus SHA256 of the complete
catalog. Unknown or altered models, rates, proof fields and expired certificates
fail closed. Production catalog entries are deliberately uncertified.

`calculate_worst_case_cost` is the central price function:

`input_limit * max_input_unit_rate + output_limit * max_output_unit_rate`.

All other billing classes must be explicitly zero/prohibited: cache read,
5-minute/1-hour cache write, server-tool request, runtime milliseconds and flat
request fees. The output class includes reasoning; it is not double-counted or
reduced to visible text. Actual usage calculation lives in the same central
module, uses exact Decimal arithmetic and never trusts provider-supplied dollars.
The full allowed input budget is reserved even when actual input is cheaper.

The only admissible test contract defines a synthetic tokenizer: one UTF-8 byte
per token plus eight framing tokens across system and user input. This is exact
by definition for the **fake**, never a Claude tokenizer claim. It expires only
as a fixture; real observed-price contracts expire on their recorded date.

`build_bounded_request` accepts exactly system text and one user text; rejects
oversized input without truncation, history, dumps over the limit and uncontrolled
extra request fields. It serializes immutable canonical bytes. Validation rebuilds
and recounts those exact bytes; token-proof or body changes invalidate admission.
The hash binds catalog digest, contract identity and complete wire request.
No model helper loads files, history, repositories, tools or queue data implicitly.

`dufynd_messages_transport.py` prepares the real POST `/v1/messages` framing and
usage parser. Its executable wrapper requires exact `httpx.MockTransport`; no
socket factory, credential lookup, environment switch, redirect or SDK retry is
available. Simulation uses an invalid fixture model and dummy key. It is complete
transport preparation, not a real-provider certification or enabled paid path.

The existing `BoundedProviderAdapter` remains the only orchestration path:

1. Build and validate immutable request; calculate deterministic worst case.
2. Existing atomic `reserve_dufynd_model_call` RPC.
3. Existing one-time `dispatch_dufynd_model_call` RPC.
4. One mock HTTP send, no retries/fallbacks.
5. Validate all usage classes; existing settlement RPC with receipt, token counts,
   request hash, catalog version/hash and bound evidence.

No new database/budget/dispatch architecture is introduced. Existing provider
contracts reserve their configured full envelope maximum. A live real contract
must eventually match the same catalog certificate and have its own new approved
budget; this phase installs neither.

## Failures, tests and fully simulated canary

- Crash before reservation: no claim or provider send.
- Crash after reservation, before dispatch: TTL releases undispatched reserve.
- Lost dispatch acknowledgement: no automatic send; dispatched reserve charges
  maximum at TTL, even if no charge actually occurred.
- Lost/unclear provider response: charge maximum; never infer zero cost.
- Response received, settlement missing: TTL charges maximum; late verified usage
  may lower it through existing recovery, without reopening dispatch.
- Retry same request: existing idempotency and one-time dispatch prohibit billing
  a second time. Altered request/certificate cannot reuse the same key.
- Unknown or out-of-bound usage, new billing class, caching, reasoning outside the
  output count: conservative maximum charge; no provider retry.

Unit tests cover exact costs/counts, input boundary, hard output/reasoning limit,
unknown model/rates, tampering, real-contract closure, network rejection, price
margin of $0.000001, shared reservations/retries and the historical Nightshift.
The PostgreSQL CI service also runs the prepared transport with HTTP mocks through
**the actual existing SQL RPCs**, including crash TTL and successful settlement.
Its synthetic capacity windows are explicitly dry-run, without owner decision
references; no spend approval is created or simulated for the canary.

Run `python -m scripts.dufynd_simulated_provider_canary` without credentials.
Expected: one mock call; zero real calls/cost, reserve $0.000896, simulated usage
$0.000148, release $0.000748; duplicate retry has no second dispatch; a $0.000001
shortfall is rejected before HTTP. The CLI uses scripted RPC mocks; real admission
and recovery are independently proven by the PostgreSQL job.

## OPTIMIZATION_CANDIDATE

- Obtain a provider-guaranteed input tokenizer/upper-bound contract and a
  request-accepted rate ceiling. This is required certification work, not a reason
  to reuse the old SDK or exhausted budget.
- Revisit an OpenRouter pinned, non-reasoning open-model route only with verified
  tokenizer revision, full prompt template/overhead and complete billing classes.
- Unify future real and database contract hashes with an immutable versioned
  registry migration before enabling any contract. Currently no real contract
  exists, so a registry mismatch cannot authorize real execution.
- Replace conservative crash charges only with verified provider receipts.

STOP after post-merge verification and simulated canary. First real call requires
new explicit owner budget authorization after the technical blocker is resolved.
