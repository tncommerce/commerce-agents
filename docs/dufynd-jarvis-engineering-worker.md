# DUFYND Jarvis Engineering Worker v1

The engineering worker is a guarded patch-preparation component for DUFYND Jarvis.
It is intentionally **not** a deployment or GitHub-writing agent.

## Purpose

The worker can inspect the current repository, prepare narrowly scoped technical
changes in a disposable GitHub Actions checkout, run non-executing static checks,
and return a patch artifact for later validation and promotion.

The worker does not push commits, open or merge pull requests, deploy services,
publish content, mutate production data, buy anything, or send external messages.

## Tool surface

Jarvis receives only custom MCP tools for:

- loading the repository-derived DUFYND master status
- bounded text-file reads
- bounded literal text search
- UTF-8 writes inside approved engineering paths
- exact text replacement inside approved engineering paths
- `git status`, `git diff --no-ext-diff`, Ruff lint and Ruff format checks

There is no raw Bash tool and no generic process-execution tool exposed to the
model.

## Write boundary

Approved write areas are limited to:

- `scripts/`
- `tests/`
- `docs/`
- `examples/retail/api/`
- selected storefront source/test directories

The worker rejects writes to GitHub workflows, canonical DUFYND data,
`supabase/`, dependency manifests, lockfiles, environment files, credentials,
private keys and paths outside the repository.

The Actions runner independently validates the final changed-path set after the
model exits. This is a second boundary in addition to the model tool policy.

## Code execution boundary

The model may not run `pytest`, `scripts/check.py` or arbitrary repository
code after it has edited files. That would allow edited code to become an
execution escape from the tool allowlist.

v1 therefore permits only non-executing static checks during patch preparation.
Executable validation belongs in a separate future sandbox with no credentials,
no GitHub write token and no network.

## GitHub boundary

The workflow has `contents: read` only and checkout persistence of Git
credentials is disabled. The worker cannot push or merge.

A successful `prepare-patch` run produces only:

- `dufynd-engineering.patch`
- `dufynd-engineering-status.txt`
- `dufynd-engineering-stat.txt`

The artifact is retained for seven days and the patch is capped at 2 MiB.

## Financial boundary

Active model execution is disabled by default. A paid patch run requires:

- explicit `GO-JARVIS-ENGINEERING`
- an explicit active Jarvis budget-window ID
- configured model and Anthropic credentials
- configured server-side Supabase credentials

The per-run model cap defaults to USD 0.25 and is also clamped to the budget
window's actual remaining USD amount. Engineering runs are recorded under the
canonical `jarvis` agent name with `run_type=engineering_patch`, so the
existing Supabase budget function counts them against the same aggregate Jarvis
window.

## Workflow modes

`readiness` is the default and performs no model execution.

`prepare-patch` requires the explicit approval token, budget ID and task. It
runs the worker, validates that all changed paths stay within the approved
engineering scope, checks patch whitespace, enforces the artifact-size limit,
and uploads the disposable patch artifact.

## Promotion path

v1 deliberately stops before promotion. A later component may validate the patch
in an isolated execution sandbox, review policy/evidence, create a dedicated
branch/PR and eventually merge to `scentai-mvp` under the configured approval
policy. `main`, secrets, contracts, spending and destructive production actions
remain separate owner gates.
