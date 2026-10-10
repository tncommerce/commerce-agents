# Private delivery and retry recovery

`python -m scripts.dufynd_media_handoff SOURCE.mp4 --directory PRIVATE_CACHE
--sha256 EXPECTED_SHA256` stages already materialized Library/Drive media on the
existing publisher host. No network call, public URL, reencoding or approval is
created. Use the returned `path` as the existing publisher's local media input;
its platform audit and independently verified hosted-URL/Owner-GO gates still
apply. A local cache is not a replacement for the durable original archive.

The cache must be owner-only. Files are streamed, bounded to 300 MB, SHA checked,
fsynced, installed without replacement and read-only. Concurrent handoffs reuse
the same verified file. Changed sources, symlinks, unsafe permissions and corrupt
existing entries fail closed; partial copies are removed. This enables private
native file handoff without provisioning another service. It does not establish
Instagram 24-fps acceptance or authorize automatic/public delivery.

Analytics generates one UUID per browser action and retains it across the
existing bounded transport retry. The API namespaces it by the stable funnel
identity. Supabase's existing unique event_id constraint and PostgREST
`on_conflict=event_id` with `resolution=ignore-duplicates` retain the first event;
repeated delivery never overwrites source attribution or QA classification.
Local JSONL remains diagnostic fallback, not the authoritative visitor counter.
Legacy clients without a key retain existing behavior. Clickout-generated IDs
and affiliate targets are unchanged.

Jarvis continues its bounded two-task batch after a handler error only when the
existing fenced failure RPC confirms the execution is durably stale. The failed
task remains for the existing supervisor to recover from its checkpoint. No
immediate retry or new scheduler is added. Missing failure acknowledgement or
uncertain finalization still stops the runner. The CLI exits unsuccessfully if
any task was deferred, even if another task completed; CI cannot report a false
clean run. Error details remain type-only.
