# SCENTAI Research Trigger System

Status: active
Updated: 2026-09-18

## Purpose

The research-trigger system converts repeated zero-result catalog searches into
internal research signals. It does not create products, change prices, attach
affiliate links, or publish anything automatically.

## Trigger thresholds

### WATCH
- at least 1 zero-result search
- from at least 1 anonymous session

Meaning:
- weak signal
- monitor only
- do not add a candidate solely because of one search

### RESEARCH
- at least 3 zero-result searches
- from at least 2 distinct anonymous zero-result sessions

Meaning:
- actionable research signal
- prioritize evidence review when the term points to an open backlog candidate
- create a manual research lead when the term is not in the backlog

### HIGH
- at least 7 zero-result searches
- from at least 4 distinct anonymous zero-result sessions

Meaning:
- strong first-party catalog-gap signal
- move the research investigation near the top of the queue
- still requires normal identity, demand, community and commerce verification

## Classification

Each trigger is classified before action:

- `live_catalog`
  - the fragrance already exists live
  - repeated no-results indicate a search/relevance/filtering problem, not a
    missing product

- `verified_staging`
  - the fragrance is already verified and waiting on promotion blockers
  - repeated demand can justify prioritizing the existing affiliate/image
    blockers

- `research_backlog`
  - the fragrance already exists in the not-yet-staged candidate backlog
  - repeated demand can raise its research priority

- `new_research_opportunity`
  - the search term matches neither live catalog, staging nor backlog
  - create only a manual research lead; no product identity is inferred

## Run the report

From a trusted environment with SCENTAI Supabase credentials:

```powershell
python scripts/report_scentai_research_triggers.py
```

Machine-readable output:

```powershell
python scripts/report_scentai_research_triggers.py --machine-readable
```

Save a snapshot:

```powershell
python scripts/report_scentai_research_triggers.py --output examples/retail/data/scentai_research_trigger_snapshot.json
```

## Guardrails

- Triggering is based on zero-result sessions, not only raw event counts.
- One user's repeated activity must not be mistaken for broad demand.
- A trigger is a research signal, not a product fact.
- No-result demand never creates a product automatically.
- No-result demand never bypasses identity verification.
- No-result demand never bypasses image, merchant, affiliate, staging QA or
  live-promotion gates.
- Affiliate commission never affects trigger strength or ordering.
