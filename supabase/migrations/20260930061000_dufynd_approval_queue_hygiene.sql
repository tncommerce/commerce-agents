-- DUFYND Jarvis approval-queue hygiene.
-- Keeps historical human-gated tasks out of the active approval boundary.
begin;

create or replace function public.get_dufynd_autonomy_queue()
returns jsonb language sql stable security invoker set search_path to 'public'
as $function$
select jsonb_build_object(
  'safe_to_execute', coalesce((
    select jsonb_agg(to_jsonb(t) order by t.priority desc, t.task_id)
    from public.dufynd_autonomy_tasks t
    where t.status = 'ready' and not t.requires_human_approval
  ), '[]'::jsonb),
  'in_progress', coalesce((
    select jsonb_agg(to_jsonb(t) order by t.priority desc, t.task_id)
    from public.dufynd_autonomy_tasks t where t.status = 'in_progress'
  ), '[]'::jsonb),
  'waiting_human_input', coalesce((
    select jsonb_agg(to_jsonb(t) order by t.priority desc, t.task_id)
    from public.dufynd_autonomy_tasks t where t.status = 'waiting_human_input'
  ), '[]'::jsonb),
  'waiting_external', coalesce((
    select jsonb_agg(to_jsonb(t) order by t.priority desc, t.task_id)
    from public.dufynd_autonomy_tasks t where t.status = 'waiting_external'
  ), '[]'::jsonb),
  'blocked', coalesce((
    select jsonb_agg(to_jsonb(t) order by t.priority desc, t.task_id)
    from public.dufynd_autonomy_tasks t where t.status = 'blocked'
  ), '[]'::jsonb),
  'approval_required', coalesce((
    select jsonb_agg(to_jsonb(t) order by t.priority desc, t.task_id)
    from public.dufynd_autonomy_tasks t
    where t.status = 'approval_required'
       or (
         t.requires_human_approval
         and t.status = any (array['planned'::text, 'ready'::text, 'in_progress'::text])
       )
  ), '[]'::jsonb),
  'done_recent', coalesce((
    select jsonb_agg(to_jsonb(x) order by x.updated_at desc)
    from (
      select * from public.dufynd_autonomy_tasks where status = 'done'
      order by updated_at desc limit 20
    ) x
  ), '[]'::jsonb)
);
$function$;

commit;
