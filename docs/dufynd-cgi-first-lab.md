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


## LAB 02 — improved offline optics, still NO GO (17.10.2026)

The existing free CPU renderer now has a real wall-dependent 3D meniscus and ray-solved normal, a chamfered cap with analytically bounded raymarch, a correctly lowered closed cap over the nozzle, and physically linked spectral-opacity straight-alpha reconstruction. This removes the former ghostlike light-glass rectangle when compositing against dark backgrounds; it is not a CSS/glow substitute for optical glass. An exact-source SHA-256, image SHA-256, pose, alpha bounds and \`INTERNAL_NOT_APPROVED\` evidence file are generated alongside each *local* PNG. Realpath output validation and a fail-closed 6px image-edge check protect the public asset tree.

**Executed visual and technical research:** Original closed 850×960/6-sample and open 700×760/6-sample renders, separately inspected. Closed and opened smaller proof renders have transparent corners, an opaque label/cap and silhouette bounds [92,52,386,477] and [110,18,368,477] respectively at 480×530. Python bytecode compilation passed. A combined two-render command exceeded the terminal wrapper time; separately the high-resolution poses completed in around 21s and 16s. No browser QA or licensed merchant image was involved; the script remains excluded from builds/CI/runtime and the results are **not promoted** to storefront posters.

**Independent hold:** Real meniscus/cap curvature and compositing are better, but studio lighting remains visually synthetic. The research bottle is still a filleted box, not exactly the live q=.60 superellipse; a separate exact-q prototype was rejected for exaggerated foot caustics. Do not claim photorealism, 9.5/10, true physical device-GPU testing or owner approval. Prioritize original high-end CGI asset art direction, then live-scene geometry matching, then closed/open poster and 1440/390/320 device QA; never pay for external assets/credits without authorization.

## LAB 03 — pose parity study (internal, 17 October 2026)

**Status: independent CGI study, NOT_FINAL_YET.** Exact controlled opening poses are a prerequisite for matching any approved still to the existing responsive WebGL. The original LAB02 renderer erroneously used a fixed cap travel `0.74` and lateral shift `0.27`, while Three.js uses `0.74 / 0.78 / 1.04` cap lift at 320/390/desktop and `0.34` x shift. The atomizer's separate rings did not form a visually cohesive group when the cap opened.

LAB03 now has an optional `--viewport-width 320|390|1440` (default 320, independent of output PNG pixel size). The cap lift and atomizer lift now match the **existing** WebGL values `0.74/.78/1.04` and `0.24/.33/.46`, respectively; the collar, rim and nozzle rise together, while the underlying fixed glass neck remains on the vessel. Desktop reference camera/framing expands only when the cap opens to avoid cropping its larger lift. Local evidence JSON records the actual reference viewport width and both rises; no public WebGL source code changes were made.

**Executed isolated optical renders** on the research CPU, each at 480×530, 2 samples: 1440-open bbox `[129,42,349,462]`, 390-open bbox `[110,12,368,477]`, 320-open bbox `[110,17,368,477]`, 390-closed bbox `[92,52,386,477]`. Every state has transparent corners, a true opaque metal/label pixel and at least the required six-pixel border; each local run emitted source/image hashes. A first desktop-camera test correctly **failed** the clipping guard; the framed follow-up passed without weakening it. The offline rendered bottle/glass still does **not** use the exact q=.60 live vessel shape, and these previews are not evidence of photorealistic CGI or Safari GPU performance.

**Rejected without promotion:** an isolated q=.60 smooth-superellipse SDF still produced overly graphic, bright glass-foot caustics; substituting gaussian studio softboxes softened some cap reflection bands but left the synthetic central amber and studio feel. Neither experimental technique was committed. The core blockers remain the art-directed luxury CGI still, material geometry parity and owner-quality review >=9.5 per critical visual area, not simply more shaders.

This is optional internal R&D only; `.cgi-lab/` outputs remain ignored, never promoted into public fallbacks, CI builds or production without separate verified review.
