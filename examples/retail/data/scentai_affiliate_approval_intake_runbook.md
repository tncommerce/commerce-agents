# SCENTAI Affiliate Approval Intake Runbook

Status: prepared
Updated: 2026-09-19

## Purpose

Use this procedure when an affiliate network changes the status of a SCENTAI
merchant program, especially when Douglas or Flaconi is approved.

The approval event changes program state only. It does **not** enable live
affiliate routing.

## 1. Create a non-secret intake file

Copy:

`examples/retail/data/scentai_affiliate_approval_intake.example.json`

Fill only observable program facts:
- exact normalized merchant ID
- exact network name
- exact registered program name
- observed network decision
- observation time
- non-secret evidence reference
- whether deeplinks/feed/tracked URLs/images appear to be available

Never enter:
- passwords
- access or refresh tokens
- API keys
- client secrets
- credential values
- private feed URLs

Secrets belong only in the approved external secret store / deployment
environment.

## 2. Validate before changing registry state

Run:

```powershell
python scripts/validate_scentai_affiliate_approval_intake.py --intake <INTAKE_FILE>
```

A valid approval must result in:
- `observed_status=approved`
- `activation_state_after_event=approved_credentials_pending`
- `live_routing_allowed_after_event=false`

If validation fails, stop. Do not manually bypass the failure.

## 3. Record the network decision

After a valid intake:
- append a new immutable event to
  `scentai_affiliate_program_events.json`
- update the matching current program status in
  `scentai_affiliate_programs.json`
- run
  `scripts/validate_scentai_affiliate_program_events.py`

The event ledger and current registry must agree.

## 4. Rebuild Jarvis operational queues

Rebuild:
- merchant mapping work queue
- affiliate activation status
- Release 01 feed activation queue
- Release 01 gate status

An approved Douglas or Flaconi program with full Release 01 mapping should
unlock a **feed-validation path**, not live routing.

## 5. Verify credentials outside Git

Confirm required credentials are present in the deployment/secret environment.
Never serialize secret values into JSON, logs, tests, screenshots or commits.

Transition:
`approved_credentials_pending -> approved_integration_pending`

## 6. Obtain a real approved feed or tracked-link sample

Do not assume Awin/CJ field names.

Create a provider config from the real sample using:
`scentai_affiliate_provider_config.example.json`

Then run the read-only Release 01 checker:

```powershell
python scripts/check_scentai_release_feed.py --feed <LOCAL_FEED_FILE> --provider-config <PROVIDER_CONFIG>
```

Raw/private feed files stay out of source control.

## 7. Dry-run import and image extraction

Run the existing merchant import in dry-run mode and extract feed image
candidates.

No offer write and no image approval occurs automatically.

## 8. Manual visual approval

Every Release 01 image must match:
- fragrance
- concentration
- bottle size / canonical variant
- current edition

Reject gift sets, testers, refills, legacy variants and generated bottle
lookalikes.

Final image approval remains a human/user gate.

## 9. Promotion dry-run

Only after current tracked offers and approved images exist:

```powershell
python scripts/promote_scentai_catalog.py --manifest examples/retail/data/scentai_release_batch_01.json
```

Expected result before any live write:
- 5 ready
- 0 blocked

## 10. Explicit user approval before live activation

The future Jarvis may prepare every prior step automatically.

It must stop at:
`ready_for_user_approval`

Only explicit user approval may transition to:
`active`

Affiliate commission never influences fragrance recommendation ranking. For equal customer totals within the same freshness band, a valid affiliate route is preferred; among affiliate routes commission may break the tie.
