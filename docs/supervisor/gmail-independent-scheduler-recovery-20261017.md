# DUFYND private Gmail refresh: independent Cloud Scheduler boundary

**Status:** proposal and isolated code only. OFF by default, no new resource deployed, no live credential touched. Owner/technical review required before any private broker release.

## What is actually broken (17 October 2026)

- Three narrowly scoped Gmail thread observers are blocked in Supabase as `blocked_configuration / credential_expired`.
- Last successful private observer capture occurred at 2026-10-17 19:42:50 UTC.
- Last GitHub Actions schedule-to-dispatch chain occurred at 19:41:53 -> 19:41:59 UTC.
- The private access-token expiry was 20:23:21 UTC, after an authorized 19:23:22 UTC refresh.
- GitHub Actions CI continued via PR events, but the GitHub `schedule` events stalled.
- The ordinary OAuth access-token lifetime of roughly one hour is expected; the problem is *refresh trigger freshness*, not proof of revoked consent or a demand for reauthorization.
- The two Github workflow schedules and watchdog share the same GitHub scheduler dependency. They are not truly independent. No claims about GitHub internal root cause without GitHub incident evidence.

## Exact proposed change

Google Cloud Scheduler invokes `POST /internal/gmail/refresh` on the already isolated Google Cloud Run private broker. The scheduled request presents a Google-signed OIDC ID token **only** for the pinned service account `BROKER_GMAIL_SCHEDULER_SA_EMAIL`, audience `BROKER_ORIGIN + /internal/gmail/refresh`, Google issuer and verification keys, acceptable lifetime and age. There is no shared secret, GitHub token, arbitrary webhook or untrusted query payload.

- Feature is **off by default**. Without the pinned email and verified scheduler identity, 403. No scheduler role is granted inside the broker.
- Calls `GmailRefreshBroker.refresh()` **only**: uses encrypted Google Cloud Firestore/Secret Manager broker vault, lock/CAS and the existing Gmail scope/account/refresh-token checks.
- HTTP response contains no provider data (204), no thread messages, no tokens, no account identifiers or internal function output.
- The Github-OIDC `read -> ingest -> ack -> finalize` boundary and current `/v1/gmail/threads/{id}` endpoints are unchanged.
- Google scheduler tokens are rejected on every other endpoint, including `/v1/health`, Gmail metadata, ack and Owner routes. Github OIDC tokens are rejected on the Scheduler endpoint.
- Invalid grant/revocation still requires a separate deduplicated Owner consent decision. Never set credential statuses to healthy manually.
- A Cloud Scheduler trigger **is not an independent Supabase ingestion path**. It keeps the private Gmail broker's credential valid even when GitHub schedules are delayed; the actual observational captures still need the GitHub OIDC workflow to run. This limitation is intentional and should not be misrepresented.

## Safety and costs — deployment HOLD

Google Cloud Scheduler offers **three free jobs per Google Cloud billing account** according to [Google's pricing](https://cloud.google.com/scheduler/pricing). The quota covers all projects in the *same* billing account, including paused jobs. Extra jobs cost US$0.10 per 31 days. We **have not verified the current owner's billing account, existing number of jobs, Cloud Run consumption or Cloud Scheduler permissions**, so the 0-EUR condition is **not yet verified**. Neither this PR nor its tests can create any billable resource.

**Do not deploy** until a human operator confirms all of the following:

1. The existing isolated Google Cloud project and service are owner-authorized, with no outstanding pricing / quota uncertainty. Cloud Scheduler job fits demonstrably inside the remaining free quota and Cloud Run usage remains within acceptable existing free/paid budget.
2. There is no competing technical Work/PR changing the broker runtime, Google Cloud IAM, schedule and environment. PRs #799 (visual), #800 (purchase hotfix), #801 (supervisor no-op) stay untouched. Use a dedicated change review.
3. Owner creates a dedicated Google service account *inside the existing broker project*, grants no database/Firestore/Secret Manager access, and pins its exact email in `BROKER_GMAIL_SCHEDULER_SA_EMAIL`. The Cloud Scheduler API can mint OIDC for that service account. No Owner key, Gmail refresh token or secret moves into GitHub or Supabase.
4. Deploy the **reviewed broker image digest** with the disabled-by-default code and exact service-account email. Existing callback privacy and logging safeguards must not be relaxed. Scheduler job must not log Authorization, request body, query, or response details.
5. Only after code review and cost verification, create **one** Cloud Scheduler authenticated HTTP job with this known URL/identity and fixed policy. Do not run any Terraform, CLI or console command using template placeholders.

### Configuration example (do not execute until gates pass)

```shell
gcloud scheduler jobs create http dufynd-gmail-keepalive \
  --project=OWNER_PRIVATE_PROJECT \
  --location=OWNER_PROJECT_REGION \
  --schedule="*/5 * * * *" \
  --time-zone="Etc/UTC" \
  --uri="https://OWNER_BROKER_HOST/internal/gmail/refresh" \
  --http-method=POST \
  --oidc-service-account-email="OWNER_PINNED_SCHEDULER_SA@OWNER_PRIVATE_PROJECT.iam.gserviceaccount.com" \
  --oidc-token-audience="https://OWNER_BROKER_HOST/internal/gmail/refresh" \
  --max-retry-attempts=1
```

The pinned scheduler account must match broker environment `BROKER_GMAIL_SCHEDULER_SA_EMAIL` exactly. If the Cloud Run transport later requires Cloud Run Invoker IAM, grant only the minimal appropriate service-level role. The app enforces its own OIDC boundary regardless.

## Acceptance criteria before calling anything "fixed"

1. Reviewer checks the new Google-identity path does not weaken GitHub OIDC, Owner auth, callback logging exclusions, encrypted vault, arbitrary operations or commit rights.
2. Offline CI validates: correct identity triggers a single refresh; invalid audience/issuer/email/signature/age/method/disable and any other route return 403; duplicate request is idempotent and no cursor/ack is performed; no secret returns.
3. Under an authorized owner-run staging broker, observe the first 204 with credential `refreshed_at` advancing and future `expires_at`. Repeat over **at least two natural ~1h expiry windows** without restarting the broker.
4. On the existing GitHub Actions observer pipeline, independently prove a real newer read->ingest->ack->finalize and all three Supabase observer statuses fresh with no failed/blocked dependencies. Only then claim *the complete observer* healthy.
5. If the Github scheduler remains stalled, keep business fallback via connected ChatGPT Gmail for the three **named** merchant threads. Do not claim this repairs Supabase or Observer.
6. If no free tier is available or the owner lacks GCP role, **HOLD** without creating anything. Escalate one precise decision instead of recurring failed attempts.

## Rollback

Remove the `BROKER_GMAIL_SCHEDULER_SA_EMAIL` environment value and deploy the previous owner-approved broker image digest. Disable/delete the single Google Cloud Scheduler job (after checking billing policy). GitHub's original OIDC workflow remains unchanged throughout. Do **not** revoke Gmail consent or alter the private OAuth secret as a rollback shortcut.

## Exact file ownership

- New: `private_broker/scheduler_oidc.py`, `tests/test_private_broker_scheduler_refresh.py`
- Narrow update: `private_broker/runtime.py` and optional broker deployment template comment.
- This PR does **not** change `scentai-mvp`, `main`, `dufynd_autonomy_tasks`, `cron.job`, `dufynd_observer_credentials`, `scripts/dufynd_observer_credentials.py`, any GitHub Actions workflow, or any social/commerce data.
