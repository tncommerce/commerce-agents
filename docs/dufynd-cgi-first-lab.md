# DUFYND — CGI-first optics LAB 01

**Status:** INTERNAL R&D / NOT_FINAL_YET / no release or owner visual approval  
**Date:** 2026-10-17  
**PR:** #799 (draft)  
**Budget:** 0 € additional; no external images, generation credits, product models or paid APIs.

## Why this exists

The live Three.js bottle is technically stable, recognizable and responsive. Independent closed/open captures at 1440/390/320 remain visibly below the owner's **9.5/10 in every critical visual area** because thin-wall glass and amber lack high-end product-CGI depth. The optional CC0 HDRI and cavity V4 experiments passed their respective browser tests but **failed independent visual comparison** (especially rectangular artifacts in V4). Repeating tint, flat rim highlights or tiny shader patches is not an acceptable next solution.

Follow the existing LOCAL WEB `docs/SPATIAL_CGI_LAB_01.md` learning: **art direction → convincing original CGI still → web choreography → selective live 3D**. A moving object cannot compensate for an unconvincing still.

## Internal offline reference renderer

`examples/retail/storefront-web/scripts/cgi-first-physical-still-lab.py`

Python 3 + NumPy + Numba + Pillow, run only **on demand, locally**:

```sh
python -m pip install numpy numba pillow
cd examples/retail/storefront-web
python scripts/cgi-first-physical-still-lab.py --width 850 --height 960 --samples 6 --out .cgi-lab/closed.png
python scripts/cgi-first-physical-still-lab.py --width 850 --height 960 --samples 6 --open --out .cgi-lab/open.png
```

The tool writes straight-alpha RGBA PNG and an editorial-background JPEG preview into `.cgi-lab/` (not `public/`). Its input validation prevents accidental output to the storefront's `public/` tree. It is **not** part of any existing build, deployment, CI, scheduled worker, Cron or public runtime.

All visuals are generated from local original geometry: rounded 3D glass vessel and cavity, separate amber refractive medium with spectral Beer–Lambert absorption, analytic Fresnel/refraction, studio card reflections, simple metal cap and an internally generated DUFYND study label. No claimed branded product photography or merchant destination. This is offline *reference* rendering, not a licensed photograph or production product model.

## Independent research evaluation

Proof rendered locally on 2026-10-17:

- Closed: 850 × 960, 6 samples; manually reviewed against the currently approved **technical baseline**.
- Open: 700 × 760, 6 samples; first crop exposed cap clipping, corrected the research camera framing; opened state now stays within the image.
- The separate volume produces stronger amber absorption and a visible heavy-glass foot compared with the existing realtime hero.
- **VISUAL HOLD:** Studio-light gradients and specular response still have a synthetic, straight-edged quality. The opaque black/gold cap and label are not high-end CGI; the opened pose is schematic. Current `rounded-box` reference geometry is *not identical* to the live renderer's rounded-square superellipse, and the alpha matte is an approximation. This is deliberately **not rated 9.5**.
- Both stills were **not promoted** to public fallback assets. A screenshot test and syntactically correct script do not establish aesthetic quality.

The research generator is an optional technical foundation; it is *not* an alternative visual result to display to the owner. Do not imply Blender/Cycles-level realism or hardware-GPU fidelity from this CPU sample.

## Acceptance gate before any integration

1. Obtain an art-directed original still with convincing optically thin glass, nonflat amber, coherent free surface, strong but plausible reflections and a luxury-cap silhouette, **at closed AND open poses**.
2. Match the still to the same approved 3D proportions, material direction, bottle label and cap movement in the live renderer; no disconnected CGI poster.
3. Use genuine transparent alpha, inspect extracted edges on both ivory and dark test surfaces; confirm no DOM text contamination or fringing.
4. Independently inspect 1440/390/320 full viewport, object close-ups, opened/closed, reduced-motion, no-JS and software/low-end fallback; no visible clipping.
5. After a genuinely superior original image pair passes quality review, replace the two existing fallback posters **together**, on this branch only; run the existing QA without weakening assertions.
6. Preserve Rabanne RC1, published products, merchant photos/rights, catalogue, consent, analytics and attribution. Merge and production deploy require separate owner approval.

**Current release decision: NO GO** for this CGI still. PR #799 stays draft. No production mutation and no spend.