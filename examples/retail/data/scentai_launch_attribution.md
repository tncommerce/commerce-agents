# SCENTAI Launch Attribution

Status: prepared
Updated: 2026-09-19

## Goal

Measure which organic launch content actually moves visitors deeper into
SCENTAI without using third-party advertising trackers or storing personal
identity data.

The attribution model separates:
- landing page
- acquisition channel
- campaign ID
- content ID

These identifiers persist only for the current browser tab/session and are
attached to first-party SCENTAI analytics events.

## Supported channels

Use one of:
- `tiktok`
- `instagram`
- `youtube`
- `organic`
- `newsletter`
- `partner`

Unknown channels are ignored by the storefront.

## URL format

SCENTAI acquisition links use:

```text
?src=<channel>&cmp=<campaign_id>&content=<content_id>
```

Example:

```text
/parfum-alternativen?src=tiktok&cmp=launch01&content=imagination_dupe_03
```

## Naming convention

Use short stable identifiers only.

Campaign IDs:
- `launch01`
- `winter26`
- `gift26`

Content IDs should identify the individual creative, not the viewer.

Recommended pattern:

```text
<format>_<topic>_<sequence>
```

Examples:
- `original_vs_alt_imagination_01`
- `top3_office_02`
- `dupe_battle_althair_01`
- `gift_guide_women_01`
- `scentai_decides_date_03`

Do not put names, emails, phone numbers or other personal data in campaign or
content identifiers.

## Build a tracked link

From the repository root:

```powershell
python scripts/build_scentai_campaign_link.py --base-url https://YOUR-SCENTAI-DOMAIN --landing /parfum-alternativen --channel tiktok --campaign launch01 --content original_vs_alt_imagination_01
```

If `NEXT_PUBLIC_SITE_URL` is configured, `--base-url` can be omitted.

## What is measured

The session attribution follows later first-party events, including:
- consultation starts
- recommendation views
- fragrance detail views
- comparisons
- merchant clickouts

The reporting view groups performance by:
- landing page
- channel
- campaign
- content ID

This lets SCENTAI identify content formats that generate meaningful product
engagement instead of optimizing only for social-platform views.

## Interpretation guardrails

- A clickout is not a verified sale.
- Small samples remain directional.
- Content attribution must not influence fragrance recommendation ranking.
- Affiliate commission must not influence content-performance interpretation.
- Do not treat one strong video as proof that the fragrance itself is
  universally better.


## Export the full pre-launch link set

The prepared launch plan contains 15 creatives and the three organic launch
channels TikTok, Instagram and YouTube.

Generate every standardized link variant with:

```powershell
python scripts/export_scentai_launch_links.py --base-url https://YOUR-SCENTAI-DOMAIN --output examples/retail/data/scentai_launch_links.local.json
```

This produces 45 links: one link for each creative/channel combination.

The generated local link export should be treated as an operating artifact,
not as product data. Regenerate it whenever the canonical domain, campaign or
content plan changes.
