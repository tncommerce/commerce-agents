-- One PostgreSQL statement: guards and DDL succeed or roll back together.
do $dufynd_atomic_migration$
begin
  execute $dufynd_migration_payload$
set local lock_timeout='2s';
set local statement_timeout='30s';
-- Rollback preflight. Catalog checks only: no planner invocation and no business-row writes.
do $dufynd_release_guard$
declare p pg_proc%rowtype;
begin
  if current_user <> 'postgres' then
    raise exception 'DUFYND release guard: execute as the verified postgres owner';
  end if;

  if not pg_try_advisory_xact_lock(hashtext('dufynd-autonomous-business-planner-v1')) then
    raise exception 'DUFYND release guard: planner currently running; transaction aborted';
  end if;

  select * into p from pg_proc where oid=to_regprocedure('public.plan_dufynd_autonomous_business_work_v1()');
  if not found or md5(pg_get_functiondef(p.oid)) is distinct from '8668638435b216b4c0dd9fa535448669' then
    raise exception 'DUFYND release guard: unexpected function definition: public.plan_dufynd_autonomous_business_work_v1()';
  end if;
  if pg_get_userbyid(p.proowner)<>'postgres' or p.prosecdef or
     p.proconfig is distinct from array['search_path=public']::text[] or
     obj_description(p.oid,'pg_proc') is not null or
     (select array_agg(a::text order by a::text) from unnest(p.proacl) a)
       is distinct from array['postgres=X/postgres','service_role=X/postgres']::text[] then
    raise exception 'DUFYND release guard: unexpected owner, ACL, invoker mode, search path or comment: public.plan_dufynd_autonomous_business_work_v1()';
  end if;

  select * into p from pg_proc where oid=to_regprocedure('public.read_dufynd_business_source_v1(jsonb)');
  if not found or md5(pg_get_functiondef(p.oid)) is distinct from '6b8852a51087ba57bf2222481e651bc7' then
    raise exception 'DUFYND release guard: unexpected function definition: public.read_dufynd_business_source_v1(jsonb)';
  end if;
  if pg_get_userbyid(p.proowner)<>'postgres' or p.prosecdef or
     p.proconfig is distinct from array['search_path=public']::text[] or
     obj_description(p.oid,'pg_proc') is not null or
     (select array_agg(a::text order by a::text) from unnest(p.proacl) a)
       is distinct from array['postgres=X/postgres','service_role=X/postgres']::text[] then
    raise exception 'DUFYND release guard: unexpected owner, ACL, invoker mode, search path or comment: public.read_dufynd_business_source_v1(jsonb)';
  end if;
end;
$dufynd_release_guard$;

CREATE OR REPLACE FUNCTION public.plan_dufynd_autonomous_business_work_v1()
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
declare
  q jsonb;
  fm jsonb;
  move text;
  created jsonb := '[]'::jsonb;
  tid text;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-autonomous-business-planner-v1'));
  q := public.get_dufynd_next_autonomous_action();

  if q->>'state' in ('work_available','work_in_progress','owner_gate') then
    return jsonb_build_object(
      'version',2,'state',q->>'state','action','none',
      'reason','existing_work_or_gate_already_explains_next_step',
      'created_tasks',created,'paid_calls',0,'new_spend_usd',0
    );
  end if;

  fm := public.read_dufynd_first_money_runtime();

  if coalesce((fm->>'publication_verified')::boolean,false)=false then
    move := 'social_publication_readiness';

    tid := 'bizplan:social-truth:'||to_char(now() at time zone 'UTC','YYYYMMDDHH24');
    insert into public.dufynd_autonomy_tasks(
      task_id,domain,title,instruction,status,priority,budget_class,
      resource_scope,durability_policy,durable_payload,forbidden_actions
    ) values(
      tid,'supervisor','Verify social publication readiness truth',
      'Persist current First-Money publication, funnel and supervisor evidence only. Never publish or schedule content.',
      'ready',100,'free','["db:jarvis.supervisor_v2.health"]'::jsonb,'durable',
      '{"kind":"supervisor_state_audit","steps":1,"interval_seconds":2}'::jsonb,
      '["social.publish","gmail.send","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
    ) on conflict(task_id) do nothing;
    if found then created := created || jsonb_build_array(tid); end if;

    tid := 'bizplan:creative-recovery:'||to_char(now() at time zone 'UTC','YYYYMMDD');
    insert into public.dufynd_autonomy_tasks(
      task_id,domain,title,instruction,status,priority,budget_class,
      resource_scope,durability_policy,durable_payload,forbidden_actions
    ) values(
      tid,'content','Build zero-spend content reuse shortlist',
      'Rank existing DUFYND social assets using stored quality evidence. Do not generate, schedule, publish, message or modify approved assets.',
      'ready',95,'free','["db:dufynd.content_assets","db:dufynd.content_reuse"]'::jsonb,'durable',
      '{"kind":"content_reuse_shortlist","version":1}'::jsonb,
      '["social.publish","gmail.send","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
    ) on conflict(task_id) do nothing;
    if found then created := created || jsonb_build_array(tid); end if;

  elsif fm->>'next_evidence'='qualified_session' then
    move := 'qualified_traffic_generation';
    tid := 'bizplan:funnel-truth:'||to_char(now() at time zone 'UTC','YYYYMMDDHH24');
    insert into public.dufynd_autonomy_tasks(
      task_id,domain,title,instruction,status,priority,budget_class,
      resource_scope,durability_policy,durable_payload,forbidden_actions
    ) values(
      tid,'supervisor','Audit qualified-traffic readiness',
      'Persist bounded funnel and supervisor evidence; identify missing internal prerequisites only. Do not create traffic, publish, message or spend.',
      'ready',90,'free','["db:jarvis.supervisor_v2.health"]'::jsonb,'durable',
      '{"kind":"supervisor_state_audit","steps":1,"interval_seconds":2}'::jsonb,
      '["social.publish","gmail.send","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
    ) on conflict(task_id) do nothing;
    if found then created := created || jsonb_build_array(tid); end if;
  else
    move := 'business_reprioritization';
  end if;

  q := public.get_dufynd_next_autonomous_action();
  return jsonb_build_object(
    'version',2,'state',case when jsonb_array_length(created)>0 then 'work_planned' else 'planner_gap' end,
    'action','bounded_business_planning','business_next_move',move,
    'created_tasks',created,'queue',q,'paid_calls',0,'new_spend_usd',0,
    'owner_action_required',false
  );
end;
$function$
;

-- Rollback postflight; helper remains private and inert. Catalog checks only: no planner invocation and no business-row writes.
do $dufynd_release_guard$
declare p pg_proc%rowtype;
begin
  if current_user <> 'postgres' then
    raise exception 'DUFYND release guard: execute as the verified postgres owner';
  end if;

  select * into p from pg_proc where oid=to_regprocedure('public.plan_dufynd_autonomous_business_work_v1()');
  if not found or md5(pg_get_functiondef(p.oid)) is distinct from '229acd42dc117f9419a750aa3b52f67c' then
    raise exception 'DUFYND release guard: unexpected function definition: public.plan_dufynd_autonomous_business_work_v1()';
  end if;
  if pg_get_userbyid(p.proowner)<>'postgres' or p.prosecdef or
     p.proconfig is distinct from array['search_path=public']::text[] or
     obj_description(p.oid,'pg_proc') is not null or
     (select array_agg(a::text order by a::text) from unnest(p.proacl) a)
       is distinct from array['postgres=X/postgres','service_role=X/postgres']::text[] then
    raise exception 'DUFYND release guard: unexpected owner, ACL, invoker mode, search path or comment: public.plan_dufynd_autonomous_business_work_v1()';
  end if;

  select * into p from pg_proc where oid=to_regprocedure('public.read_dufynd_business_source_v1(jsonb)');
  if not found or md5(pg_get_functiondef(p.oid)) is distinct from '6b8852a51087ba57bf2222481e651bc7' then
    raise exception 'DUFYND release guard: unexpected function definition: public.read_dufynd_business_source_v1(jsonb)';
  end if;
  if pg_get_userbyid(p.proowner)<>'postgres' or p.prosecdef or
     p.proconfig is distinct from array['search_path=public']::text[] or
     obj_description(p.oid,'pg_proc') is not null or
     (select array_agg(a::text order by a::text) from unnest(p.proacl) a)
       is distinct from array['postgres=X/postgres','service_role=X/postgres']::text[] then
    raise exception 'DUFYND release guard: unexpected owner, ACL, invoker mode, search path or comment: public.read_dufynd_business_source_v1(jsonb)';
  end if;
end;
$dufynd_release_guard$;

$dufynd_migration_payload$;
end;
$dufynd_atomic_migration$;
