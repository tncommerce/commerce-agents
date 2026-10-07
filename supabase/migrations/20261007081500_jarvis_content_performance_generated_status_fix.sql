-- Jarvis V5.2.1: respect generated dufynd_jarvis_inbox.processing_status.
-- The live column is derived and must never be assigned directly.

create or replace function public.run_dufynd_content_performance_worker_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  t public.dufynd_autonomy_tasks;
  token uuid := gen_random_uuid();
  claimed jsonb;
  audit jsonb;
  evidence text;
  ok boolean;
  processed_events integer := 0;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-content-performance-worker-v1'));

  select q.* into t
  from public.dufynd_autonomy_tasks q
  where q.status='ready'
    and q.domain='content'
    and q.budget_class='free'
    and not q.provider_cost_unknown
    and not q.requires_human_approval
    and not q.external_review_required
    and not q.needs_freshness_recheck
    and q.durable_payload->>'kind'='content_performance_learning'
    and q.resource_scope='["db:dufynd.content_performance","db:dufynd.jarvis_inbox","db:dufynd.content_learning"]'::jsonb
    and public.dufynd_capability_list_valid(q.required_capabilities)
    and public.dufynd_capability_list_valid(q.forbidden_actions)
  order by q.priority desc,q.created_at,q.task_id
  limit 1
  for update;

  if t.task_id is null then
    return jsonb_build_object('version',1,'status','idle','reason','no_content_performance_task','new_spend_usd',0);
  end if;

  claimed := public.claim_dufynd_worker_v2(t.task_id,'content_performance_worker_v1',token);
  if claimed is null then
    return jsonb_build_object('version',1,'status','not_claimed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  ok := public.update_dufynd_worker_v2(
    t.task_id,token,'working','Aggregating latest DUFYND social performance evidence.',null
  );
  if not ok then
    return jsonb_build_object('version',1,'status','claim_update_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  audit := public.read_dufynd_content_performance_learning_v1();
  evidence := 'Content performance learning: '||audit::text;

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.content_performance_learning_v1','content',audit,91,now())
  on conflict(key) do update
  set value=excluded.value,priority=excluded.priority,last_verified_at=excluded.last_verified_at;

  with claimed_events as (
    select inbox_id
    from public.dufynd_jarvis_inbox
    where event_type='content_performance_added'
      and source_type='content_performance'
      and status='pending'
      and fingerprint is null
    order by inbox_id
    limit 200
    for update skip locked
  ), updated as (
    update public.dufynd_jarvis_inbox j
    set status='done',
        processed_at=now(),
        attempts=j.attempts+1,
        last_error=null,
        updated_at=now()
    from claimed_events c
    where j.inbox_id=c.inbox_id
    returning j.inbox_id
  )
  select count(*)::integer into processed_events from updated;

  ok := public.update_dufynd_worker_v2(t.task_id,token,'verifying',evidence,null);
  if not ok then
    return jsonb_build_object('version',1,'status','verification_transition_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  ok := public.update_dufynd_worker_v2(t.task_id,token,'done',evidence,null);
  if not ok then
    return jsonb_build_object('version',1,'status','completion_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  return jsonb_build_object(
    'version',1,'status','completed','task_id',t.task_id,
    'processed_events',processed_events,'audit',audit,'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.run_dufynd_content_performance_worker_v1() from public, anon, authenticated;
grant execute on function public.run_dufynd_content_performance_worker_v1() to service_role, postgres;

do $$
declare generated_kind text;
begin
  select is_generated into generated_kind
  from information_schema.columns
  where table_schema='public'
    and table_name='dufynd_jarvis_inbox'
    and column_name='processing_status';

  if generated_kind is distinct from 'ALWAYS' then
    raise exception 'expected dufynd_jarvis_inbox.processing_status to be generated ALWAYS';
  end if;
end
$$;
