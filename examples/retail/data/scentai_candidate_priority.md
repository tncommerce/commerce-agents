# SCENTAI Candidate Priority

Status: active
Updated: 2026-09-18

## Purpose

This workflow prioritizes fragrance research using first-party SCENTAI
catalog-demand signals without bypassing the existing selection policy or
promotion gates.

It does not make products live.

## Current backlog state

At the time this workflow was introduced:
- 54 candidates exist in the candidate backlog
- 30 of those candidates are already present in verified staging
- 24 candidates remain in the not-yet-staged research queue

Candidates already in staging are excluded from research prioritization.

## Demand score

The internal SCENTAI demand score is 0-10 and uses:
- search frequency: up to 4 points
- unique-session proxy: up to 3 points
- no-result pressure: up to 3 points

The score is intentionally conservative. A single search can surface a signal,
but stronger priority requires repeated demand and/or multiple anonymous
sessions.

## Relationship to the 0-100 selection policy

The established 0-100 selection weights remain unchanged:
- retailer demand: 35
- community strength: 30
- cross-merchant coverage: 15
- trend momentum: 10
- portfolio fit: 10

If a candidate has verified numeric `selection_score_components`, first-party
SCENTAI demand may increase only the existing `trend_momentum` component and
never above 10.

If the backlog record has no numeric selection score, SCENTAI keeps the demand
score separate. It does not invent retailer, community, merchant, trend or
portfolio evidence.

## Matching behavior

Demand is matched against:
- canonical fragrance name
- brand + fragrance name
- conservative brand abbreviations such as YSL, JPG and PDM

Loose matching is intentionally restricted to reduce false positives.
Very short names such as `Y` require a stronger brand/name match.

## New opportunity discovery

Search terms that do not match any existing research candidate are surfaced in
`unmatched_demand_terms`.

These terms are research leads only. They do not create catalog products,
identities, relationships, prices or affiliate offers automatically.

## Run the priority report

From a trusted environment with the SCENTAI Supabase credentials:

```powershell
python scripts/prioritize_scentai_candidates.py
```

Machine-readable output:

```powershell
python scripts/prioritize_scentai_candidates.py --machine-readable
```

Save a snapshot:

```powershell
python scripts/prioritize_scentai_candidates.py --output examples/retail/data/scentai_candidate_priority_snapshot.json
```

Offline/test mode accepts a JSON file containing a `search_rows` array:

```powershell
python scripts/prioritize_scentai_candidates.py --demand-json PATH_TO_DEMAND_ROWS.json
```

## Guardrails

- Affiliate commission never affects demand or candidate priority.
- Research priority is not publication approval.
- Staged candidates are not researched again by this queue.
- No-result searches do not verify product identity.
- Personal data is not used for candidate ranking.
- Normal identity, scent, image, merchant, affiliate, QA and promotion gates
  remain mandatory before live publication.
