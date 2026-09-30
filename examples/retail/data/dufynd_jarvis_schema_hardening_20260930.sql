-- DUFYND Jarvis control-plane hardening (2026-09-30)
--
-- The Nightshift outcome protocol includes a task-local "blocked" state, but the
-- production dufynd_autonomy_tasks CHECK constraint originally omitted it.
-- This patch is idempotent and only broadens the accepted status set; it does
-- not mutate existing task rows.

begin;

alter table public.dufynd_autonomy_tasks
  drop constraint if exists dufynd_autonomy_tasks_status_check;

alter table public.dufynd_autonomy_tasks
  add constraint dufynd_autonomy_tasks_status_check
  check (
    status = any (
      array[
        'planned'::text,
        'ready'::text,
        'in_progress'::text,
        'waiting_human_input'::text,
        'waiting_external'::text,
        'approval_required'::text,
        'blocked'::text,
        'done'::text,
        'cancelled'::text
      ]
    )
  );

commit;
