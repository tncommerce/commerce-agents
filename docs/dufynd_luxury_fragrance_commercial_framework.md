# DUFYND Luxury Fragrance Commercial Framework v1

Status: canonical reusable production framework
Source basis: user-provided Byredo Bal d'Afrique Absolu example, 2026-09-22
Purpose: reusable logic for DUFYND fragrance shorts/commercials. Adapt product facts, materials, notes, mood and brand language to each fragrance. Do not copy brand-specific creative details blindly.

## Core production logic

### Step 1 — Character sheet / technical blueprint for cross-shot continuity

Before video generation, create one professional product design character sheet that acts as the canonical visual identity reference across all shots.

Required principles:
- All views show the exact same single product instance.
- Preserve identical colors, proportions, materials, silhouette and label placement.
- Use a clean horizontal 16:9 blueprint layout.
- Central row contains five views on a controlled dark/black background:
  1. 3/4 L
  2. HERO
  3. SIDE
  4. BACK
  5. MACRO
- Product only: no hands, props, packaging or stray reflections.
- HERO must show the front label clearly.
- MACRO should capture the most identity-defining material/detail area.
- Add technical labels and metadata around the sheet:
  - brand
  - character-sheet version
  - category
  - color palette with hex values
  - materials/texture swatches
  - dimensions
  - model/tracking code
- Render direction:
  - photorealistic high-end studio product photography
  - even three-point softbox illumination
  - gentle rim light
  - grounding shadows
  - macro sharpness
  - ultra-clean frame purity

Purpose:
This sheet is the product identity anchor. Later prompts should reference it as the canonical source (e.g. @sheet) so the bottle is not re-invented shot by shot.

### Step 2 — Timecoded campaign generation

Generate the commercial as a precise timecoded shot list rather than one vague visual prompt.

Rules:
- Define total duration and aspect ratio first.
- Define one coherent world/mood for the fragrance.
- Use hard cuts where appropriate when the intended style calls for it; avoid accidental transitions.
- Explicitly repeat product-continuity constraints:
  - same bottle shape
  - same liquid color
  - same cap
  - same label
  - same proportions
- Each shot has:
  - exact start timestamp
  - shot scale (macro / medium hero / wide / top-down / detail)
  - subject
  - environment
  - lighting
  - camera angle
  - camera movement
- Favor luxury camera language:
  - slow push-in
  - faint micro-drift
  - gentle upward drift
  - almost-static hold
  - controlled hero shot
- Alternate product shots with fragrance-world shots:
  - environment / atmosphere
  - ingredient macro
  - product hero
  - nature/material macro
  - product detail
  - closing hero
- Maintain one controlled palette throughout.
- End with explicit constraints such as:
  - cinematic
  - photorealistic
  - luxury perfume campaign
  - no distortion
  - maintain product proportions
  - steady motion
  - muted / controlled colors

Key lesson:
The video is designed as a sequence of individual shots, not as one generic “make it cinematic” request.

### Step 3 — Post-generation text integration pass

After the base video is satisfactory, preserve it exactly and add text as a separate edit/generation pass.

Required preservation language:
- keep every shot
- keep every subject
- keep every camera move
- keep timing unchanged
- keep color unchanged
- do not regenerate
- do not reorder
- do not replace
- do not restyle
- constant frame rate
- no freeze frames
- no duplicated frames
- no skipped/repeated frames
- no stutter
- no jitter
- no speed changes
- no time remapping

Text design:
- elegant minimal typography
- thin, letter-spaced sans-serif
- color matched to campaign palette
- text placed in apparent 3D space behind the main subject when useful
- subject partially occludes text
- text slightly softer than foreground when visually behind the subject
- gentle fade in/out
- one caption per intended shot
- no unnecessary boxes, headers or graphic clutter

Purpose:
Protect the successful video while adding editorial typography without re-generating the visual foundation.

### Step 3.1 — Minimal effect / final hero pass

If a final refinement is needed, preserve the video exactly again and add only one or two carefully scoped elements.

Examples:
- one subtle fragrance-release light/smoke effect
- one final note-family caption behind the hero product
- one final brand/creative line in open negative space

Rules:
- effects must remain subtle
- do not alter product identity
- do not disturb camera motion
- do not restyle or regenerate scenes
- avoid stacking multiple visual effects
- final text should feel integrated into the composition

## DUFYND operating principles derived from the example

1. **Identity first.** Build the product sheet before the video.
2. **Prompt by shot.** Use timestamps and explicit camera instructions.
3. **One visual world.** Palette, lighting and environment remain coherent.
4. **Macro + hero alternation.** Ingredient/material/world shots create sensorial storytelling; hero shots anchor product recognition.
5. **Controlled motion beats spectacle.** Luxury comes from deliberate movement, not constant effects.
6. **Separate generation from finishing.** First create a clean base video; then add text/effects in preservation passes.
7. **Repeat continuity constraints.** Never assume the model will remember exact bottle details.
8. **Use product-specific truth.** Adapt liquid color, materials, cap, label, note imagery and setting to the actual fragrance.
9. **No blind imitation.** Borrow the production logic, not another brand’s exact visual identity.
10. **Spend credits after references are strong.** Better references + controlled prompts usually beat expensive generation on weak inputs.

## Reusable DUFYND prompt architecture

### A. CHARACTER SHEET
- Subject definition
- Exact bottle/material/liquid/cap/label description
- 5 canonical views
- technical palette/material/dimension blocks
- studio-lighting/render constraints

### B. CAMPAIGN SHOTLIST
- campaign name + duration + aspect ratio
- canonical product reference = @sheet
- product continuity paragraph
- timecoded shots
- environment + ingredients + product detail + hero shots
- camera movement per shot
- palette + realism + no-distortion constraints

### C. TEXT PASS
- preserve base video exactly
- typography specification
- 3D placement / occlusion logic
- shot-specific captions only

### D. FINAL EFFECT PASS
- preserve base video exactly
- only one subtle effect and/or final caption
- no restyling, retiming or scene replacement

## Application to Bois Impérial

For Bois Impérial specifically, adapt the framework toward:
- clear/neutral liquid
- exact Essential Parfums bottle and cap geometry
- cool green-black / dry wood / mineral / aromatic world
- controlled product macros
- woody/mineral/aromatic ingredient or texture shots
- premium editorial camera movement
- minimal sound design
- no blue liquid
- no bottle morphing
- no extra bottles
- no hands or spraying unless intentionally required
- no mismatched visual world between hero and supporting shots

This file is the reusable canonical reference for future DUFYND fragrance-commercial prompting.
