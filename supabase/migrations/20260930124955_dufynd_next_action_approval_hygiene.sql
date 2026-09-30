-- DUFYND Jarvis next-action approval-count hygiene.
-- Historical completed human-gated tasks must not look like active approvals.
begin;

create or replace function public.get_dufynd_next_autonomous_action()
returns jsonb
language sql
stable
set search_path to 'public'
as $function$
with next_task as (
  select to_jsonb(t) as task
  from public.dufynd_autonomy_tasks t
  where t.status='ready'
    and not t.requires_human_approval
  order by t.priority desc, t.updated_at asc, t.task_id
  limit 1
),
counts as (
  select
    count(*) filter (where status='ready' and not requires_human_approval) as ready_count,
    count(*) filter (where status='waiting_human_input') as waiting_human_count,
    count(*) filter (where status='waiting_external') as waiting_external_count,
    count(*) filter (
      where status='approval_required'
         or (
           requires_human_approval
           and status = any (array['planned'::text, 'ready'::text, 'in_progress'::text])
         )
    ) as approval_count
  from public.dufynd_autonomy_tasks
)
select jsonb_build_object(
  'next_task', (select task from next_task),
  'ready_count', ready_count,
  'waiting_human_count', waiting_human_count,
  'waiting_external_count', waiting_external_count,
  'approval_count', approval_count,
  'state', case
    when ready_count > 0 then 'work_available'
    when waiting_human_count > 0 or approval_count > 0 or waiting_external_count > 0 then 'at_autonomy_boundary'
    else 'idle'
  end,
  'stop_reason', case
    when ready_count > 0 then null
    when waiting_human_count > 0 then 'waiting_for_human_input'
    when approval_count > 0 then 'human_approval_required'
    when waiting_external_count > 0 then 'waiting_for_external_event'
    else 'no_open_work'
  end
)
from counts;
$function$;

commit;
