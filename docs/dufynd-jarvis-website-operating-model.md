# Jarvis website operating boundary

Jarvis is an internal operator, not the public fragrance advisor. The supported
path is observe, detect, prioritize, develop, test, browser QA, draft PR, release
approval, production. A configured capability is not evidence that a worker ran.

1. Existing observers and the production smoke inspect public production. Their
   last successful observation and freshness must both be checked.
2. Analytics analysis reads the service-only visitor projection. QA and unknown
   provenance do not establish real visitor demand; clickouts do not establish sales.
3. Affiliate work must bind approval, tracking, exact products and fresh offers to
   separate evidence. Feed access alone cannot authorize a merchant or an image.
4. The durable queue records work, blockers and approval requirements. Active model
   execution additionally requires explicit activation and an available budget.
5. Safe research workers cannot write code or run a shell. Isolated engineering
   workers prepare local patches within the existing path allowlist.
6. Deterministic validation checks paths, Python, repository contracts and, for
   storefront changes, a build and responsive browser QA before PR handoff.
7. The handoff creates only a new `jarvis/worker-*` branch and a draft PR to
   `scentai-mvp`. A changed base or another dispatch branch is rejected.
8. Production rules require a PR and passing checks; they do not require a second
   human approval. The no-auto-merge boundary therefore also depends on the
   constrained workflow and owner-controlled release process. Draft is not an ACL.
9. Render auto-deploys the production branch. Merging into that branch is therefore
   a deployment decision. This handoff has no merge, deploy or ruleset-edit action.
10. Content preparation, publishing, partner contact and spend are distinct actions.
    Research or creative approval never authorizes a publication, message, purchase,
    new subscription, scheduler activation or production database migration.

The GitHub token can write development branches and PRs. Do not describe it as
read-only or claim the ruleset mechanically requires a human review. There is no
bypass actor in the observed production ruleset. No live worker is activated by
this change; existing budget and activation gates remain in force.
