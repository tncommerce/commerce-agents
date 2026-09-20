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

For launch-specific work:

```powershell
python scripts/dufynd_jarvis_bridge.py refresh-launch-gate --machine-readable
```

The context contains:
- current master/business status
- approved creative references
- repeatable content formats
- content ideas
- durable lessons
- approval boundaries
- affiliate partner state
- recent AI-video experiments
- model/format learning aggregates
- content funnel outcomes
- launch-gate state

## Creative learning loop

For each controlled video experiment:

1. Create or reuse one content idea.
2. Keep the hypothesis and hook explicit.
3. Test the smallest useful shot before generating a full video.
4. Record the model, prompt summary, cost, result URI and quality scores.
5. Score at least:
   - scroll_stop
   - product_accuracy
   - luxury_feel
   - motion
   - rewatch
   - brand_fit
   - reproducibility
6. Record a durable lesson only when evidence supports a reusable rule.
7. Compare model and format aggregates before choosing the next test.

Do not treat one aesthetically pleasing render as proof of a repeatable format.

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

After an affiliate approval and a real feed/export sample exist:

1. Map the real source columns into the canonical merchant contract.
2. Validate the provider config.
3. Check it against the partner/program registries.
4. Run the real-feed preflight.
5. Verify exact product mappings.
6. Run the merchant import dry-run.
7. Review feed image candidates manually.
8. Activate only after tracking and release checks pass.

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
- prepare prompts and edit plans
- compare models
- update internal experiment records
- derive internal lessons
- refresh launch readiness

Jarvis must obtain explicit human approval before:
- spending money
- buying subscriptions or credits
- publishing content
- scaling paid advertising
- important outbound messages
- contracts or supplier orders
- destructive production changes
- merging changes that materially affect the live production experience

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
