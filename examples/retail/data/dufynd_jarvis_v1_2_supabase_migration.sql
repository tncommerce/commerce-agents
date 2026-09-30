-- DUFYND Jarvis V1.2 stability migration
-- Prepared 2026-09-30. Apply only after explicit operator approval.
--
-- Aligns the Supabase autonomy-task status constraint with the Jarvis runtime.
-- Jarvis already uses "blocked" as a non-terminal, recoverable task state.

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
        'blocked'::text,
        'approval_required'::text,
        'done'::text,
        'cancelled'::text
      ]
    )
  );

commit;
