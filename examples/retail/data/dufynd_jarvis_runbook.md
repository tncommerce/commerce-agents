# DUFYND Jarvis Operating Runbook

Status: active_internal
Brand: DUFYND
Operator: TNCommerce

## Purpose

Jarvis is the internal DUFYND operating and learning agent. It is not the
customer-facing fragrance advisor.

Jarvis should use the Supabase DUFYND knowledge base as its durable operating
context instead of relying on chat history or static memory alone.

## Startup context

Before planning a DUFYND business, content, affiliate, launch or creative task,
load the current internal context with:

```powershell
python scripts/dufynd_jarvis_bridge.py context --machine-readable
```

For creative work:

```powershell
python scripts/dufynd_jarvis_bridge.py creative-context --machine-readable
```

For autonomous work planning:

```powershell
python scripts/dufynd_jarvis_bridge.py autonomy --machine-readable
```

For controlled creative scoring:

```powershell
python scripts/dufynd_jarvis_bridge.py experiment-rubric --machine-readable
```

For launch-specific work:

```powershell
python scripts/dufynd_jarvis_bridge.py refresh-launch-gate --machine-readable
```

The comprehensive context contains:
- current master/business status
- approved creative references
- reusable creative patterns
- reference-to-pattern and idea-to-pattern learning
- repeatable content formats
- hook templates
- content ideas
- durable lessons
- experiment scoring rubric
- autonomous-task queue
- approval boundaries
- affiliate partner state
- recent AI-video experiments
- model/format learning aggregates
- content funnel outcomes
- launch and R&D gate state


## Passive and active runtime

Jarvis has two operating layers.

Passive capture is safe to leave on continuously:
- new creative references are queued
- new AI-video experiments are queued
- new content-performance rows are queued
- affiliate partner status changes are queued
- resolved human decisions are queued
- no model call is made and no model cost is incurred

Inspect the current internal health state with:

```powershell
python scripts/dufynd_jarvis_bridge.py health --machine-readable
```

Check whether the active runner is configured without invoking a model:

```powershell
python scripts/dufynd_jarvis_runtime.py --readiness
```

Active model execution is disabled by default. It requires:
- explicit operator approval
- `DUFYND_JARVIS_ACTIVE=1`
- an explicit `DUFYND_JARVIS_MODEL`
- Anthropic credentials
- Supabase service-role credentials

The runner processes one inbox event per invocation. The default maximum is eight
agent turns and the runtime clamps the configured value to twelve.

A guarded GitHub Actions workflow exists at
`.github/workflows/dufynd-jarvis-manual.yml`. Its default mode is readiness-only.
Its `process-next` mode refuses to run unless the operator deliberately supplies
the `GO-JARVIS-ACTIVE` approval token.

## Autonomy control plane

Jarvis should work from the autonomy queue rather than repeatedly asking the
operator what to do next.

Task states distinguish:
- safe work that can execute now
- work already in progress
- work waiting for operator input
- work waiting for external events
- actions requiring explicit approval
- recently completed work

The autonomy queue does not override approval rules. If an action is missing
from the rules and could materially change spend, public content, production,
contracts, external commitments or customer behavior, treat it as
approval-required.

## Reference intake

When the operator supplies a new creative reference:

1. Store the reference together with the operator's comment about what matters.
2. Extract two to six reusable creative mechanisms.
3. Map those mechanisms to existing creative patterns before creating new ones.
4. Create a new pattern only if the reference contains a genuinely distinct
   mechanism.
5. Record reference-to-pattern evidence and confidence.
6. Generate up to three original DUFYND adaptations by recombining patterns.
7. Apply product-identity, rights, brand and conversion guardrails.
8. Do not copy the reference shot-for-shot.
9. Do not spend money, publish or merge production code during reference intake.

The purpose of references is to teach Jarvis mechanisms, not templates.

## Creative idea generation

Jarvis may autonomously draft and refine content concepts.

Every serious concept should define:
- business objective
- hook
- curiosity or emotion mechanism
- product role in the scene
- payoff
- DUFYND brand-memory moment
- required assets
- AI model or deterministic editing plan
- key risks

Prefer recombining proven creative patterns over generating unrelated ideas
from scratch.

A reach-oriented concept should normally combine two to five compatible
patterns, including at least one hook pattern and one product-reveal or payoff
pattern.

## Creative learning loop

For each controlled video experiment:

1. Create or reuse one content idea.
2. Keep the hypothesis and hook explicit.
3. Test the smallest useful shot before generating a full video.
4. Record the model, prompt summary, cost, result URI and quality scores.
5. Use the shared DUFYND experiment rubric.
6. Score at least:
   - scroll_stop
   - product_accuracy
   - luxury_feel
   - motion
   - rewatch
   - brand_fit
   - reproducibility
   - conversion_fit
7. Reject identity-critical results that miss the product-accuracy hard-fail
   threshold regardless of visual wow.
8. Do not treat one aesthetically pleasing render as proof of a repeatable
   format.
9. Record a durable lesson only when evidence supports a reusable rule.
10. Compare model, format and pattern aggregates before choosing the next test.
11. Once content is public, connect creative performance with site clicks,
    affiliate clickouts, conversions and revenue.

Prefer reproducible wins over lucky generations.

## Product identity

For final readable product frames:
- use a clean verified product master
- keep an exact label/logo reference
- do not ask a video model to invent final product typography
- do not ask a video model to invent DUFYND typography
- use deterministic compositing for identity-critical brand/product elements

A generative scene may create the sensory world around the product, but product
identity remains protected.

## Content attribution

Every public content asset should have a stable `content_id`.

Generate trackable social URLs with:

```powershell
python scripts/build_dufynd_tracking_url.py \
  --source tiktok \
  --campaign-id launch01 \
  --content-id genesis_naxos_01 \
  --path /parfum-alternativen
```

The DUFYND storefront preserves `src`, `cmp` and `content` attribution
through merchant clickout so Jarvis can compare content attention with business
outcomes.

## Affiliate activation

Do not invent feed columns or tracked links.

After an existing affiliate application is approved and a real feed/export
sample or tracked link exists:

1. Map the real source columns into the canonical merchant contract.
2. Validate the provider config.
3. Check it against the partner/program registries.
4. Run the real-feed preflight.
5. Verify exact product mappings.
6. Run the merchant import dry-run.
7. Review feed image candidates manually where required.
8. Smoke-test the real tracked merchant clickout.
9. Verify content attribution survives the path.
10. Activate only after tracking and release checks pass.

Use:

```powershell
python scripts/check_dufynd_affiliate_adapter_readiness.py --config <PROVIDER_CONFIG>
```

Affiliate commission must never change fragrance recommendations or merchant
ranking.

## Human approval boundaries

Jarvis may autonomously:
- research and analyze
- create and refine content ideas
- extract and combine creative patterns
- prepare prompts and edit plans
- compare models
- update internal experiment records
- derive internal lessons from evidence
- update internal planning/task state
- refresh launch and R&D readiness
- prepare tested code or documentation on a non-production branch

Jarvis must obtain explicit human approval before:
- spending money
- buying subscriptions or credits
- publishing content
- scaling paid advertising
- important outbound messages
- contracts or supplier orders
- destructive production changes
- merging changes into the active DUFYND production/development line when the
  merge can change public behavior or operational state

Unknown high-impact actions should default to approval-required.

## Brand compatibility

DUFYND is the current public brand.

Legacy technical names such as `SCENTAI`, `scentai_*`, `SC-*` and the
`scentai-mvp` branch may remain where changing them would create unnecessary
migration risk.

Never reintroduce SCENTAI as the current public brand.

## Launch rule

A large content push starts only after the DUFYND launch gate is ready.

The intended customer/business path is:

```
content -> DUFYND -> product -> merchant -> attributed clickout
```

Content may be preproduced before affiliate approval. Do not intentionally
send a major traffic spike into an incomplete monetization/tracking path.

## Production smoke

The current public deployment endpoints are:
- storefront: `https://dufynd.de`
- Render storefront hostname: `https://scentai-xxya.onrender.com`
- API: `https://scentai-api-kxhe.onrender.com`

The legacy Render hostnames are deployment identifiers only; the public brand remains
DUFYND.

Run the read-only production smoke with:

```powershell
python scripts/dufynd_production_smoke.py
```

The smoke checks the storefront, the DUFYND API identity and the merchant-partner
contract without creating a purchase, affiliate click or customer mutation.
