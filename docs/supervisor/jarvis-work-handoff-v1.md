# Jarvis → ChatGPT Work: manual, evidence-bound handoff V1

This feature is intentionally a **read-only owner-side handoff**. It is **not**
a dispatcher, scheduled automation, worker activation, new queue, API integration
or background ChatGPT invocation. It is a first bounded interface for giving an
external agent a task without copying untrusted free-form queue instructions.

The existing `build_operator_diagnosis` creates an optional
`work_handoff` in the existing authenticated Control Room DTO. Only the exact
business-planner state `planner_gap`, a static allowlisted goal
(`funnel_conversion_readiness` or `qualified_traffic_generation`), an
explicit capability gap, fresh operational sources and a business checkpoint
not older than one hour can enable it. Current owner gates, active runs and
ready engineering/commerce/web/platform work suppress it. Readiness of an
unrelated certified free *supervisor* task is not falsely classified as a web
engineer. Every refusal is `status=unavailable`; no workflow is dispatched.

The brief is authored in source code from fixed templates. No database task
instruction, chat history, arbitrary URL, credential or unverified prose is
included. It instructs Work to re-check live repository/PR state, respect the
current branch, check for same-scope work, make one verifiable improvement only,
run the existing responsive/attribution/consent QA, and stop at the Owner's
release/spend/publishing gates. Zero spending is a requirement, not a statement
of any account-level Work entitlement. The interface copies the brief only
on a direct owner click. Copy failure is surfaced; it never claims to have
started an external session.

Production remains unchanged until a separately reviewed merge/deploy. Adding
this to Draft PR #799 creates no new Supabase cron, handler, service, permission
or paid model call.

**Limitations:** This cannot launch or resume a ChatGPT Work session on its own.
It also cannot promise a continuously working Jarvis agent. Autonomous dispatch
requires an explicitly supported agent interface, scoped credentials, freshness/
deduplication controls, a cost policy and a distinct Owner authorization; do not
simulate that capability by firing generic events or paid model calls.

Verification: tests in `tests/test_jarvis_operator.py` assert permitted
handoff, missing/unknown capability, staleness, Owner gate, duplicate engineering
work and unrelated supervisor-ready work. Existing owner Control Room and
downstream browser tests must continue to pass. No 9.5/10 visual approval is
inferred from these tests.
