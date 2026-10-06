-- Jarvis V4.5: first productive zero-spend business worker.
-- Builds a deterministic reuse shortlist from existing DUFYND content assets.
-- No generation, publishing, outreach, credentials, model calls, spend or main changes.

create or replace function public.read_dufynd_content_reuse_audit_v1()
returns jsonb
language sql
stable
set search_path to 'public'
as $function$
with scored as (
  select
    a.id,
    a.content_id,
    a.asset_type,
    a.status,
    a.uri,
    a.metadata->>'title' as title,
    case
      when coalesce(a.metadata->>'hero_review_score','') ~ '^[0-9]+([.][0-9]+)?$'
        then (a.metadata->>'hero_review_score')::numeric
      when coalesce(a.metadata->>'material_world_champion_score','') ~ '^[0-9]+([.][0-9]+)?$'
        then (a.metadata->>'material_world_champion_score')::numeric
      when coalesce(a.metadata->>'assistant_score','') ~ '^[0-9]+([.][0-9]+)?$'
        then (a.metadata->>'assistant_score')::numeric
      else null
    end as explicit_score,
    (a.metadata->>'quality_review'='pass' and a.metadata->>'visual_qa'='pass') as legacy_quality_pass,
    coalesce((a.metadata->>'operator_concept_approved')::boolean,false) as operator_concept_approved,
    coalesce((a.metadata->>'publishing_approved')::boolean,false) as publishing_approved
  from public.dufynd_content_assets a
  where a.status in ('ready_to_publish','draft')
),
eligible as (
  select *,
    case
      when explicit_score >= 9.5 then 'meets_current_9_5'
      when explicit_score >= 8.5 then 'below_current_9_5'
      when legacy_quality_pass then 'legacy_quality_pass_recheck_required'
      else 'insufficient_quality_evidence'
    end as current_standard_status
  from scored
  where explicit_score >= 8.5
     or legacy_quality_pass
     or operator_concept_approved
),
ranked as (
  select *
  from eligible
  order by
    (explicit_score >= 9.5) desc nulls last,
    legacy_quality_pass desc,
    operator_concept_approved desc,
    explicit_score desc nulls last,
    id
  limit 12
)
select jsonb_build_object(
  'version',1,
  'observed_at',now(),
  'source','dufynd_content_assets',
  'policy','reuse_existing_assets_only_no_generation_no_publish',
  'current_quality_floor',9.5,
  'candidate_count',(select count(*) from eligible),
  'explicit_9_5_count',(select count(*) from eligible where explicit_score >= 9.5),
  'legacy_recheck_count',(select count(*) from eligible where current_standard_status='legacy_quality_pass_recheck_required'),
  'publishing_approved_count',(select count(*) from eligible where publishing_approved),
  'requires_current_visual_recheck',true,
  'decision',case
    when exists(select 1 from eligible where explicit_score >= 9.5) then 'current_9_5_master_available'
    when exists(select 1 from eligible) then 'reuse_candidates_available_but_recheck_required'
    else 'no_reusable_asset_evidence'
  end,
  'candidates',coalesce((
    select jsonb_agg(jsonb_build_object(
      'asset_id',id,
      'content_id',content_id,
      'asset_type',asset_type,
      'status',status,
      'uri',uri,
      'title',title,
      'explicit_score',explicit_score,
      'legacy_quality_pass',legacy_quality_pass,
      'operator_concept_approved',operator_concept_approved,
      'publishing_approved',publishing_approved,
      'current_standard_status',current_standard_status
    ) order by
      (explicit_score >= 9.5) desc nulls last,
      legacy_quality_pass desc,
      operator_concept_approved desc,
      explicit_score desc nulls last,
      id)
    from ranked
  ),'[]'::jsonb),
  'next_move','Use this shortlist as zero-spend source material. Current visual recheck remains mandatory before any publish decision.',
  'new_spend_usd',0
);
$function$;

revoke execute on function public.read_dufynd_content_reuse_audit_v1() from public, anon, authenticated;
grant execute on function public.read_dufynd_content_reuse_audit_v1() to service_role, postgres;

insert into public.dufynd_handler_contracts(handler_id,handler_version,contract,enabled)
values(
  'content_reuse_shortlist',
  '1',
  jsonb_build_object(
    'handler_id','content_reuse_shortlist',
    'handler_version','1',
    'certification_status','certified',
    'risk_class','low',
    'cost_class','free',
    'durability_class','durable',
    'capabilities',jsonb_build_array('content.read','supabase.task_state','supabase.execution_state'),
    'required_capabilities',jsonb_build_array('content.read','supabase.task_state','supabase.execution_state'),
    'forbidden_actions',jsonb_build_array('gmail.send','social.publish','budget.spend','main.merge','commerce.activate','shell.execute'),
    'allowed_scopes',jsonb_build_array('content'),
    'allowed_resources',jsonb_build_array('db:dufynd.content_assets','db:dufynd.content_reuse'),
    'allowed_tools',jsonb_build_array('read_dufynd_content_reuse_audit_v1','claim_dufynd_worker_v2','update_dufynd_worker_v2'),
    'verification_policy',jsonb_build_object('kind','content_reuse_shortlist','version',1),
    'supports_retry',true,
    'supports_parallel_execution',false,
    'required_approval_class',null
  ),
  true
)
on conflict(handler_id,handler_version) do update
set contract=excluded.contract,enabled=excluded.enabled;

create or replace function public.run_dufynd_content_worker_v1()
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
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-content-reuse-worker-v1'));

  select q.* into t
  from public.dufynd_autonomy_tasks q
  where q.status='ready'
    and q.domain='content'
    and q.budget_class='free'
    and not q.provider_cost_unknown
    and not q.requires_human_approval
    and not q.external_review_required
    and not q.needs_freshness_recheck
    and q.durable_payload->>'kind'='content_reuse_shortlist'
    and q.resource_scope='["db:dufynd.content_assets","db:dufynd.content_reuse"]'::jsonb
    and public.dufynd_capability_list_valid(q.forbidden_actions)
    and jsonb_typeof(q.dependencies)='array'
    and not exists(
      select 1 from jsonb_array_elements_text(q.dependencies) d
      where not exists(
        select 1 from public.dufynd_autonomy_tasks x
        where x.task_id=d and x.status='done'
      )
    )
    and not exists(
      select 1 from public.dufynd_task_external_waits w
      where w.task_id=q.task_id and (not w.satisfied or w.policy<>'dependency')
    )
    and not coalesce(q.released_at is null and q.lease_expires_at>now(),false)
  order by q.priority desc,q.created_at,q.task_id
  limit 1
  for update;

  if t.task_id is null then
    return jsonb_build_object('version',1,'status','idle','reason','no_content_reuse_task','new_spend_usd',0);
  end if;

  claimed := public.claim_dufynd_worker_v2(t.task_id,'content_reuse_worker_v1',token);
  if claimed is null then
    return jsonb_build_object('version',1,'status','not_claimed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  ok := public.update_dufynd_worker_v2(
    t.task_id,token,'working',
    'Content reuse worker started deterministic inventory scan.',
    null
  );
  if not ok then
    return jsonb_build_object('version',1,'status','claim_update_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  audit := public.read_dufynd_content_reuse_audit_v1();
  evidence := 'Deterministic content reuse shortlist: '||audit::text;

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.content_reuse_v1','content',audit,95,now())
  on conflict(key) do update
    set value=excluded.value,priority=excluded.priority,last_verified_at=excluded.last_verified_at;

  ok := public.update_dufynd_worker_v2(t.task_id,token,'verifying',evidence,null);
  if not ok then
    return jsonb_build_object('version',1,'status','verification_transition_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  ok := public.update_dufynd_worker_v2(t.task_id,token,'done',evidence,null);
  if not ok then
    return jsonb_build_object('version',1,'status','completion_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  return jsonb_build_object(
    'version',1,
    'status','completed',
    'task_id',t.task_id,
    'worker','content_reuse_worker_v1',
    'audit',audit,
    'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.run_dufynd_content_worker_v1() from public, anon, authenticated;
grant execute on function public.run_dufynd_content_worker_v1() to service_role, postgres;

create or replace function public.plan_dufynd_autonomous_business_work_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
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
$function$;

revoke execute on function public.plan_dufynd_autonomous_business_work_v1() from public, anon, authenticated;
grant execute on function public.plan_dufynd_autonomous_business_work_v1() to service_role, postgres;

do $$
begin
  perform set_config('dufynd.worker_write','supervisor',true);

  update public.dufynd_autonomy_tasks
  set domain='content',
      title='Build zero-spend content reuse shortlist',
      instruction='Rank existing DUFYND social assets using stored quality evidence. Do not generate, schedule, publish, message or modify approved assets.',
      status='ready',
      priority=95,
      budget_class='free',
      resource_scope='["db:dufynd.content_assets","db:dufynd.content_reuse"]'::jsonb,
      durability_policy='durable',
      durable_payload='{"kind":"content_reuse_shortlist","version":1}'::jsonb,
      forbidden_actions='["social.publish","gmail.send","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb,
      worker_state='queued',
      blocked_reason=null,
      released_at=now(),
      lease_expires_at=now(),
      updated_at=now()
  where task_id='bizplan:creative-recovery:'||to_char(now() at time zone 'UTC','YYYYMMDD')
    and status<>'done';

  perform set_config('dufynd.worker_write','',true);
end
$$;

do $$
declare
  existing_job bigint;
begin
  select jobid into existing_job
  from cron.job
  where jobname='dufynd-content-reuse-worker-v1'
  order by jobid desc
  limit 1;

  if existing_job is not null then
    perform cron.unschedule(existing_job);
  end if;

  perform cron.schedule(
    'dufynd-content-reuse-worker-v1',
    '*/2 * * * *',
    'select public.run_dufynd_content_worker_v1();'
  );
end
$$;

select public.run_dufynd_content_worker_v1();
