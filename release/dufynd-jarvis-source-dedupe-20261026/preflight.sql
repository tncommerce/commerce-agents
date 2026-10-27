-- Preflight; include inside the same deployment transaction. Catalog checks only: no planner invocation and no business-row writes.
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

  -- A known inert helper may remain after the documented function-only rollback.
  if to_regprocedure('public.read_dufynd_business_source_v1(jsonb)') is not null then

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
  end if;

  if to_regprocedure('public.get_dufynd_next_autonomous_action()') is null or
     to_regprocedure('public.read_dufynd_first_money_runtime()') is null then
    raise exception 'DUFYND release guard: required planner/runtime function missing';
  end if;
  -- Parse all referenced relation fields without evaluating the business functions.
  perform key,category,value,priority,last_verified_at from public.dufynd_master_status limit 0;
  perform id,content_id,platform from public.dufynd_content_assets limit 0;
  perform asset_id,revision_fingerprint,evidence from public.dufynd_content_workflows limit 0;
  perform task_id,domain,title,instruction,status,priority,budget_class,resource_scope,
    durability_policy,durable_payload,forbidden_actions from public.dufynd_autonomy_tasks limit 0;
end;
$dufynd_release_guard$;
