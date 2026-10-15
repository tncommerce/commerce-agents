# DUFYND source-sensitive build cache correction

Development workflow change only; no trigger, permission, runner, deployment,
paid service or production behavior change.

## Observed defect

Successful CI38307331916 on `a047322931c9b96c2b5f7f87857d3496901fe45b`
logged the Next.js cache key ending in a bare hyphen after the dependency hash.
The source component was empty. The same primary-key hit prevented an updated
cache from being saved after later builds. Builds and QA still ran successfully;
this observation does not establish a stale public build or an outage.

The source pattern used brace alternatives. The actual Actions glob matcher
sets `nobrace: true`; that pattern matches zero files. GitHub documents an empty
hash for no matches and separate arguments for multiple patterns:
https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#hashfiles

## Small correction and direct proof

Only the source pattern in `.github/workflows/ci.yml` is replaced with seven
separate hashFiles arguments for js/jsx/ts/tsx/mjs/cjs/css. Dependency hash,
restore-prefix fallback and cache path stay intact. A code-sensitive primary
key can now save the updated cache after a restore-prefix fallback. The normal
cache retention/eviction rules apply; no storage allocation was added.

Using the official `@actions/glob@0.5.0` installed outside the repository with
package scripts disabled reproduced the real checkout result:

- Old source hash: empty string, exactly as seen in CI.
- New source hash: `2b36b055a0a32fbaceb57748836d90af0ff3bff0bc7a14065d35f1a102d2ee96`.
- Matched source files:182.
- Eight isolated behavioral cases pass: changing each of the seven supported
  file types changes the hash; restoring it restores the original hash; an
  unrelated text file leaves it unchanged. No production files were mutated.

The temporary verification dependency is not added to package manifests or
locks. No low-value source-text mirror test is introduced. The exact new CI
run must show a nonempty source suffix and all normal gates passing; status
and observed key are recorded in PR774 and the PR779 resume checkpoint.
No performance speedup is asserted before measurement. This corrects cache
invalidation and reuse, not the application code or release evidence.
