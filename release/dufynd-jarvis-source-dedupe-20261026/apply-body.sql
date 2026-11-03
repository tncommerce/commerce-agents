-- One PostgreSQL statement: guards and DDL succeed or roll back together.
do $dufynd_atomic_migration$
begin
  execute $dufynd_migration_payload$
set local lock_timeout='2s';
set local statement_timeout='30s';
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

-- Development only. Replace clock-generated business audits with original-data
-- transitions. No runtime/publication truth, existing task, cron or gate changes.
create or replace function public.read_dufynd_business_source_v1(p_runtime jsonb)
returns jsonb language sql stable security invoker set search_path to 'public'
as $function$
 select jsonb_build_object(
   'content_id',p_runtime->'content_id',
   'experiment_id',p_runtime->'experiment_id',
   'schedule',p_runtime->'schedule',
   'publication_verified',p_runtime->'publication_verified',
   'funnel',p_runtime->'funnel',
   'recent_signals',coalesce((select jsonb_agg(signal order by signal::text)
     from jsonb_array_elements(case when jsonb_typeof(p_runtime->'recent_signals')='array'
       then p_runtime->'recent_signals' else '[]'::jsonb end) signal),'[]'::jsonb),
   -- Rechecking identical merchant facts is not a new business signal.
   'purchase_evidence',coalesce(p_runtime->'purchase_evidence','{}'::jsonb)
     - array['last_verified_at','next_refresh_due_at','expires_at'],
   'platform_posts',coalesce((
     select jsonb_agg(facts.value order by facts.value::text)
     from public.dufynd_master_status m,
       lateral jsonb_array_elements(case when jsonb_typeof(m.value->'posts')='array'
         then m.value->'posts' else '[]'::jsonb end) post,
       lateral (select case when jsonb_typeof(post.value)='object'
         then jsonb_object_agg(field.key,field.value)
         else jsonb_build_object('invalid_post',post.value) end as value
         from jsonb_each(case when jsonb_typeof(post.value)='object'
           then post.value else '{}'::jsonb end) field where field.key in
           ('id','platform','status','scheduled_at','auto_publish','public_url','published_at')) facts
     where m.key='jarvis.thin_v1.first_money_schedule_observation'
       and m.value->>'content_id'=p_runtime->>'content_id'
       and m.value->>'experiment_id'=p_runtime->>'experiment_id'
   ),'[]'::jsonb),
   'publication_proofs',coalesce((
     select jsonb_agg(jsonb_build_object(
       'asset_id',a.id,'platform',a.platform,
       'revision_fingerprint',w.revision_fingerprint,
       'proofs',(select jsonb_object_agg(proof.key,(select case
         when jsonb_typeof(proof.value)='object' then jsonb_object_agg(field.key,field.value)
         else jsonb_build_object('invalid_proof',proof.value) end
         from jsonb_each(case when jsonb_typeof(proof.value)='object'
           then proof.value else '{}'::jsonb end) field where field.key in
           ('status','revision_fingerprint','evidence_ref','audio_playback_verified',
            'asset_sha256','platform_post_id','public_url','scheduled_at','published_at')))
         from jsonb_each(w.evidence) proof
         where proof.key in ('schedule_observation','publication_observation','publication_verification'))
     ) order by a.id)
     from public.dufynd_content_assets a
     join public.dufynd_content_workflows w on w.asset_id=a.id
     where a.content_id=p_runtime->>'content_id'
       and w.evidence ?| array['schedule_observation','publication_observation','publication_verification']
   ),'[]'::jsonb)
 );
$function$;

create or replace function public.plan_dufynd_autonomous_business_work_v1()
returns jsonb language plpgsql security invoker set search_path to 'public'
as $function$
declare
  q jsonb;
  fm jsonb;
  move text;
  created jsonb := '[]'::jsonb;
  tid text;
  audit_kind text;
  source_fingerprint text;
  checkpoint jsonb;
  unchanged boolean := false;
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
    audit_kind := 'social-truth';
  elsif fm->>'next_evidence'='qualified_session' then
    move := 'qualified_traffic_generation';
    audit_kind := 'funnel-truth';
  else
    move := 'business_reprioritization';
  end if;

  if audit_kind is not null then
    source_fingerprint := encode(sha256(convert_to(
      jsonb_build_array(audit_kind,public.read_dufynd_business_source_v1(fm))::text,
      'UTF8')),'hex');
    select value into checkpoint from public.dufynd_master_status
      where key='jarvis.business_source_dedupe_v1';
    unchanged := checkpoint->>'source_fingerprint' is not distinct from source_fingerprint;
    if not unchanged then
      -- Chaining the previous task handles real A -> B -> A transitions, while
      -- the existing lock and transaction make task+checkpoint atomic. First
      -- installation performs one bounded audit; legacy done tasks stay done.
      tid := 'bizplan:'||audit_kind||':source-v1:'||encode(sha256(convert_to(
        coalesce(checkpoint->>'task_id','')||':'||source_fingerprint,'UTF8')),'hex');
      insert into public.dufynd_autonomy_tasks(
        task_id,domain,title,instruction,status,priority,budget_class,
        resource_scope,durability_policy,durable_payload,forbidden_actions
      ) values(
        tid,'supervisor',case audit_kind when 'social-truth'
          then 'Verify social publication readiness truth' else 'Audit qualified-traffic readiness' end,
        'Persist current First-Money publication, funnel and supervisor evidence only. Never publish, schedule, generate traffic, message or spend.',
        'ready',case audit_kind when 'social-truth' then 100 else 90 end,'free',
        '["db:jarvis.supervisor_v2.health"]'::jsonb,'durable',
        '{"kind":"supervisor_state_audit","steps":1,"interval_seconds":2}'::jsonb,
        '["social.publish","gmail.send","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
      ) on conflict(task_id) do nothing;
      if found then created := created || jsonb_build_array(tid); end if;
      insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
      values('jarvis.business_source_dedupe_v1','jarvis',jsonb_build_object(
        'version',1,'source_fingerprint',source_fingerprint,'task_id',tid,
        'meaning','audit_queued_not_publication_or_execution_verified'),100,now())
      on conflict(key) do update set value=excluded.value,
        priority=excluded.priority,last_verified_at=excluded.last_verified_at;
    end if;
  end if;

  -- Preserve existing independent content planning and certified payloads.
  if coalesce((fm->>'publication_verified')::boolean,false)=false then
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
  end if;
  q := public.get_dufynd_next_autonomous_action();
  return jsonb_build_object(
    'version',2,'state',case when jsonb_array_length(created)>0 then 'work_planned' else 'planner_gap' end,
    'action','bounded_business_planning','business_next_move',move,
    'created_tasks',created,'queue',q,'paid_calls',0,'new_spend_usd',0,
    'owner_action_required',false,'source_unchanged',unchanged
  );
end;
$function$;

revoke execute on function public.read_dufynd_business_source_v1(jsonb) from public,anon,authenticated;
grant execute on function public.read_dufynd_business_source_v1(jsonb) to service_role,postgres;
revoke execute on function public.plan_dufynd_autonomous_business_work_v1() from public,anon,authenticated;
grant execute on function public.plan_dufynd_autonomous_business_work_v1() to service_role,postgres;

-- Postflight for the exact reviewed migration. Catalog checks only: no planner invocation and no business-row writes.
do $dufynd_release_guard$
declare p pg_proc%rowtype;
begin
  if current_user <> 'postgres' then
    raise exception 'DUFYND release guard: execute as the verified postgres owner';
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

$dufynd_migration_payload$;
end;
$dufynd_atomic_migration$;
