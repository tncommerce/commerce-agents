# Free pre-canary acceptance

Run without provider credentials or network calls:

```bash
python -m scripts.dufynd_free_acceptance \
  --tasks tests/fixtures/dufynd_pre_canary_real_tasks.json \
  --head "$(git rev-parse HEAD)" --output /tmp/dufynd-free-acceptance
```

The input is a sanitized snapshot of the two real tasks. This command invokes the
same `pack_evidence` used by the counted worker. The canonical context JSON is the
exact user prompt. The count-input JSON includes the real system instruction and
model settings but is **never sent**. Audit files list priorities, full-file SHA256,
provided bytes, projected fields or source line ranges, omissions and both hashes.
`packet_sha256` covers the packet before its own digest; `prompt_sha256` covers
the exact serialized prompt including that digest. Lower priority numbers win.

The 24,576-byte bound is independent of provider tokenization. Byte/4 estimates
are approximate. An official count, fresh tariff, owner authorization and atomic
reservation remain mandatory before any future real Maker request; this offline
acceptance does not authorize one or prove its actual input token count.

Attribution coverage checks actual supplied code for twelve stages, including
landing parameters, persistence, session, detail/comparison mounts, offer link,
clickout, partner tracking URL, stored offer target, server analytics and tests.
Partner URL construction and existing offer affiliate URLs are distinct paths;
coverage does not imply that every merchant dynamically receives attribution.

Content includes full hooks and voiceover scripts for all fifteen pilots, all
three voiceover specifications, bounded subtitle/social projections, three preview
inventories, pipeline, buffer, learning, QA, strategy and the high-end floor.
Column tables retain values losslessly within those explicit projections. Long
subtitles, social copy and learning documents are intentionally partial; audit
records disclose this. No media inspection or live performance evidence is implied.

The deterministic Maker selects three test candidates with literal hook citations.
It does not establish an editorial ranking or actual rendered quality. The separate
fixture checker verifies the structured citation contract, coverage, scope,
provenance and safety. It cannot approve arbitrary natural-language Maker outputs.
Tests exercise unsupported claims, missing evidence, maker/checker identity gates,
bounded rework, receipt tampering and next-safe-task proposals. Queue transitions
occur only on copied in-memory fixtures; proposing a task never dispatches it.

The controlled failure invokes the actual counted failure handler with an in-memory
bridge and disabled provider. A deliberately oversized fixture token count fails
at prepare, before reservation or provider dispatch. Its terminal receipt preserves
stage, exact reason, task, pack hash, budget, reservation/dispatch states and zero
cost. This synthetic result does not reconstruct a lost historical error reason.

No live queue, budget, approval, lease, reservation or observer state is changed.
