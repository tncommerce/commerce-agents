# DUFYND Higgsfield Prompting Standard — v1

## Purpose

This is the production prompt contract for DUFYND image/video generation.
The goal is to remove model improvisation from the parts that most strongly determine perceived quality:
camera, lens, framing, motion, lighting, material physics and continuity.

Naxos final remains the minimum premium-video quality floor.

## Core rule

Do not prompt an entire short as one concept.
Prompt every shot as a deliberately directed commercial shot.

## Shot prompt order

1. SHOT PURPOSE
   - What must the viewer understand or feel in this single shot?
   - One sentence only.

2. CAMERA POSITION
   - height;
   - distance;
   - angle;
   - axis relative to subject.

3. LENS / OPTICS
   - focal length;
   - macro vs normal;
   - depth of field;
   - focus target.

4. FRAMING
   - extreme close-up / close-up / medium / over-shoulder / top-down;
   - exact crop boundaries;
   - negative space location for text.

5. SUBJECT
   - exact object/person;
   - wardrobe/material/color;
   - what must remain unchanged.

6. MOVEMENT
   - subject movement;
   - camera movement;
   - speed and duration;
   - one principal motion only where possible.

7. LIGHTING
   - key direction;
   - rim/backlight;
   - practical lights;
   - color temperature;
   - highlight behavior.

8. MATERIAL / PHYSICS
   - how glass, liquid, mist, droplets, smoke, fabric or ingredients should behave;
   - explicitly distinguish atomized perfume mist from water jets.

9. CONTINUITY
   - what must match the previous/next shot;
   - product identity;
   - wardrobe;
   - light direction;
   - palette.

10. NEGATIVES
   - list exact failure modes;
   - ban common model shortcuts such as floor mist, fantasy aura, ribbon-like trails, warped bottle geometry, feminine wardrobe cues where inappropriate, extra limbs, split-screen graphics.

11. EXIT FRAME
   - define what the last frame should look like so the next edit/transition has a clean handoff.

## Camera language examples

### Macro atomizer
- camera: 4–7 cm from nozzle, slightly below nozzle axis;
- lens: 100mm macro equivalent;
- framing: nozzle fills upper-left/center third;
- movement: 2–3% push-in only;
- physics: cone-shaped aerosol of fine microdroplets, rapidly atomized, no continuous liquid stream;
- exit: mist disperses into negative space.

### Sillage trail
- camera: shoulder-height rear three-quarter tracking;
- lens: 50–65mm equivalent;
- framing: mid-torso to top of head, no legs/shoes unless explicitly needed;
- movement: subject walks 1–2 steps, camera tracks 3–5%;
- physics: diffuse airborne microdroplet cloud that lingers briefly in the wake, never a water jet, ribbon or floor trail;
- exit: subject leaves frame edge while cloud remains for a beat.

### Product hero
- camera: slightly below bottle shoulder line;
- lens: 70–85mm;
- framing: bottle occupies ~55–65% of frame height;
- movement: restrained orbit or push;
- lighting: hard rim + soft frontal control;
- exit: centered hero for CTA/logo.

## DUFYND style lanes

### Lane A — Ingredient Explosion / Organic Luxury
Reference direction: Bois Impérial example.

Use for:
- ingredient stories;
- note education;
- scent-family visuals;
- premium carousel covers.

Characteristics:
- central photoreal bottle;
- real ingredients suspended dynamically;
- warm dramatic lighting;
- controlled debris/droplets;
- tactile organic materials;
- no arbitrary mechanical pieces.

### Lane B — Exploded Luxury Tech
Reference direction: Clive Christian example.

Use for:
- bottle construction / identity;
- ultra-premium hero posts;
- futuristic launch visuals;
- dramatic social scroll-stoppers.

Characteristics:
- bottle decomposed into precise layers;
- glass/body/cap components separated cleanly;
- notes integrated spatially;
- deep luxury palette;
- hard specular highlights;
- technology-ad precision.

Rule:
Do not combine Lane A and Lane B by default. One dominant visual language per post.

## Video-specific rule

Generate in this order:
1. static keyframe;
2. self-review against Naxos quality floor;
3. one motion test;
4. inspect motion physics;
5. only then generate the remaining shots.

Do not spend credits on downstream shots if the first motion test fails.

## Sound rule

Sound is post-visual.
1. choose premium music;
2. cut picture to music;
3. add at most 1–3 physically motivated Foley events;
4. no homemade synthetic bed;
5. no generic SFX merely because a transition exists.

Good Foley examples:
- atomizer spray;
- real camera shutter;
- page turn;
- subtle physical whoosh tied to an object crossing frame.

## Failure conditions

Reject before operator review when:
- perfume spray reads as water jet;
- sillage reads as liquid stream;
- model adds irrelevant clothing/fashion cues;
- product geometry is visibly wrong;
- shot has infographic/template look;
- visual adds no new information or emotion;
- text boxes are carrying the concept because the image itself is weak.
