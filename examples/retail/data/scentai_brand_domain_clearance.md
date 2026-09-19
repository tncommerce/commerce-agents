# SCENTAI Brand / Domain Clearance

Status: decision_required
Updated: 2026-09-19

## Purpose

Prevent a premature custom-domain purchase or public SEO cutover before the SCENTAI naming risk is understood.

## Current findings

Public research identified multiple existing uses of the ScentAI/ScentAi name, including active fragrance-discovery services in the same broad consumer category and a separate ScentAI Inc. operating in smell/AI technology.

This does not by itself determine legal infringement or prevent use in Germany. It does create material brand-confusion, SEO-discovery and future trademark-distinctiveness risk that should be resolved before larger investment in the name.

## Domain status

- preferred candidate: scentai.de
- DNS/web checks did not show an active public site during this work block
- availability is not treated as confirmed until a registrar/registry purchase check succeeds
- no domain purchase is authorized yet
- temporary production/preview host remains https://scentai-xxya.onrender.com
- keep NEXT_PUBLIC_SITE_INDEXABLE=false until the final naming/domain decision and cutover smoke test

## Decision gate

Owner approval is required before either path:

1. keep SCENTAI after accepting/clearing the naming risk, then purchase and connect the chosen domain; or
2. rename before public launch, then update social handles, canonical URL, legal pages, partner-network profiles and launch attribution once.

## Technical readiness

The application already supports a final domain through NEXT_PUBLIC_SITE_URL. Render custom-domain cutover, canonical metadata, robots/sitemap generation, backend origin allowlisting, analytics and social attribution are prepared. No code rewrite is needed merely to change the canonical domain.

## Spend rule

Do not spend on a domain, trademark filing, paid ads or long-term brand assets until the naming decision is resolved.
