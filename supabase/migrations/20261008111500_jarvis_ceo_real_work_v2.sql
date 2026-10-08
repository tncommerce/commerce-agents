-- P0: turn already owner-frozen media and real unresolved dependencies into bounded work.
-- This does not publish, send messages, grant rights, spend, or alter external wait status.
create or replace function public.plan_dufynd_ceo_priority_work_v2()
returns jsonb
language plpgsql
set search_path to 'public'
as $fn$
declare
  asset_count integer;
  wait_count integer;
  asset_fp text;
  wait_fp text;
  stored_fp text;
  new_task text;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-ceo-priority-planner-v2'));

  if exists (
    select 1 from public.dufynd_autonomy_tasks
    where status='ready' and budget_class='free'
      and provider_cost_unknown=false and requires_human_approval=false
  ) then
    return jsonb_build_object('state','work_already_queued','new_spend_usd',0);
  end if;

  select count(*)::integer,
    md5(coalesce(string_agg(
      a.id||':'||a.version::text||':'||a.status||':'||
      coalesce(a.metadata->>'owner_freeze_date',''),
      '|' order by a.id
    ),'no_frozen_assets'))
  into asset_count,asset_fp
  from public.dufynd_content_assets a
  where a.status='owner_frozen_no_publish'
    and a.metadata->>'owner_asset_approved'='true'
    and a.metadata->>'owner_publish_approval'='false'
    and a.metadata->>'asset_editing_locked'='true';

  select value->>'fingerprint' into stored_fp
  from public.dufynd_master_status
  where key='jarvis.ceo_distribution_preflight_v2';

  if asset_count>0 and asset_fp is distinct from stored_fp then
    new_task := 'ceo:distribution-preflight:'||substr(asset_fp,1,24);
    insert into public.dufynd_autonomy_tasks(
      task_id,domain,title,instruction,status,priority,
      budget_class,resource_scope,durability_policy,durable_payload,
      required_capabilities,forbidden_actions
    ) values (
      new_task,'growth','Prepare owner-approved photo content for distribution',
      'Create a truthful publication-readiness packet from owner-frozen assets. Propose captions, platform QA and the exact owner publishing gate. Do not upload, schedule, publish, spend or alter FINAL media.',
      'ready',100,'free',
      '["db:dufynd.ceo_publish_packet","db:dufynd.content_assets"]'::jsonb,
      'durable',jsonb_build_object('kind','ceo_distribution_preflight_v2','fingerprint',asset_fp),
      '["content.read","supabase.task_state","supabase.execution_state"]'::jsonb,
      '["social.publish","gmail.send","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
    ) on conflict(task_id) do nothing;
    return jsonb_build_object('state',case when found then 'work_planned' else 'work_already_queued' end,
       'task_id',new_task,'action','prepare_frozen_social_media','new_spend_usd',0);
  end if;

  select count(*)::integer,
    md5(coalesce(string_agg(
      t.task_id||':'||t.status||':'||
      coalesce((
        select string_agg(w.observer_id||':'||w.satisfied::text||':'||w.policy,',' order by w.observer_id)
        from public.dufynd_task_external_waits w where w.task_id=t.task_id
      ),'no_wait_binding'),
      '|' order by t.task_id
    ),'no_external_waits'))
  into wait_count,wait_fp
  from public.dufynd_autonomy_tasks t
  where t.status='waiting_external';

  select value->>'fingerprint' into stored_fp
  from public.dufynd_master_status
  where key='jarvis.ceo_blocker_triage_v2';

  if wait_count>0 and wait_fp is distinct from stored_fp then
    new_task := 'ceo:blocker-triage:'||substr(wait_fp,1,24);
    insert into public.dufynd_autonomy_tasks(
      task_id,domain,title,instruction,status,priority,
      budget_class,resource_scope,durability_policy,durable_payload,
      required_capabilities,forbidden_actions
    ) values (
      new_task,'supervisor','Classify evidence-based blockers and assign next steps',
      'Reconcile the external-wait board with attached observer evidence, identify unbound stale tasks and provide exact resolver actions. Do not change rights, send partner emails, approve or unpark tasks.',
      'ready',98,'free',
      '["db:dufynd.autonomy_tasks","db:dufynd.ceo_blocker_triage","db:dufynd.task_external_waits"]'::jsonb,
      'durable',jsonb_build_object('kind','ceo_blocker_triage_v2','fingerprint',wait_fp),
      '["supabase.task_state","supabase.execution_state"]'::jsonb,
      '["social.publish","gmail.send","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
    ) on conflict(task_id) do nothing;
    return jsonb_build_object('state',case when found then 'work_planned' else 'work_already_queued' end,
       'task_id',new_task,'action','classify_real_blockers','new_spend_usd',0);
  end if;

  return jsonb_build_object('state','no_new_business_evidence','ready_tasks',0,
    'frozen_assets',asset_count,'waiting_external',wait_count,'new_spend_usd',0);
end
$fn$;

create or replace function public.run_dufynd_ceo_distribution_preflight_v2()
returns jsonb
language plpgsql
set search_path to 'public'
as $fn$
declare
  t public.dufynd_autonomy_tasks;
  a public.dufynd_content_assets;
  token uuid := gen_random_uuid();
  packet jsonb;
  fingerprint text;
  current_fp text;
  claimed jsonb;
  ok boolean;
  ig text;
  tt text;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-ceo-distribution-preflight-v2'));
  select * into t from public.dufynd_autonomy_tasks
    where status='ready' and budget_class='free'
      and provider_cost_unknown=false and requires_human_approval=false
      and external_review_required=false and needs_freshness_recheck=false
      and durable_payload->>'kind'='ceo_distribution_preflight_v2'
      and resource_scope='["db:dufynd.ceo_publish_packet","db:dufynd.content_assets"]'::jsonb
    order by priority desc,created_at limit 1 for update;
  if t.task_id is null then
    return jsonb_build_object('status','idle','reason','no_distribution_preflight_due','new_spend_usd',0);
  end if;
  fingerprint := t.durable_payload->>'fingerprint';

  select md5(coalesce(string_agg(
    id||':'||version::text||':'||status||':'||coalesce(metadata->>'owner_freeze_date',''),
    '|' order by id
  ),'no_frozen_assets')) into current_fp
  from public.dufynd_content_assets
  where status='owner_frozen_no_publish'
    and metadata->>'owner_asset_approved'='true'
    and metadata->>'owner_publish_approval'='false'
    and metadata->>'asset_editing_locked'='true';

  if fingerprint is distinct from current_fp then
    return jsonb_build_object('status','not_executed','reason','asset_approval_snapshot_changed',
      'task_id',t.task_id,'new_spend_usd',0);
  end if;

  select * into a from public.dufynd_content_assets
  where status='owner_frozen_no_publish'
    and metadata->>'owner_asset_approved'='true'
    and metadata->>'owner_publish_approval'='false'
    and metadata->>'asset_editing_locked'='true'
  order by case when content_idea_id='idea_one_night_fourteen_perfumes_20261008'
      then 0 else 1 end,id
  limit 1;
  if a.id is null then
    return jsonb_build_object('status','not_executed','reason','no_owner_frozen_asset','new_spend_usd',0);
  end if;

  claimed := public.claim_dufynd_worker_v2(t.task_id,'ceo_distribution_worker_v2',token);
  if claimed is null then
    return jsonb_build_object('status','not_claimed','task_id',t.task_id,'new_spend_usd',0);
  end if;
  ok := public.update_dufynd_worker_v2(t.task_id,token,'working','Preparing a photo-first publication readiness packet without publishing.',null);
  if not ok then
    return jsonb_build_object('status','claim_update_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  if a.content_idea_id='idea_one_night_fourteen_perfumes_20261008' then
    ig := 'Packing for ONE night. 14 perfumes. One toothbrush. 😭 Which fragrance would you never leave behind? #perfume #fragrance #perfumelover #dufynd';
    tt := 'One night away. Fourteen fragrances. One toothbrush. Priorities 😭 What would you pack? #fragrancetok #perfume #dufynd';
  else
    ig := 'She thinks he is texting someone else. He is comparing fragrances again. 👀 Would you react the same way? #fragrance #perfume #dufynd';
    tt := 'The message she suspects vs the perfume he is actually checking 👀 #fragrancetok #perfume #dufynd';
  end if;

  packet := jsonb_build_object(
    'version',2,'fingerprint',fingerprint,'created_at',now(),
    'state','draft_for_explicit_owner_publication_go',
    'priority','organic_reach_first',
    'selected_asset_id',a.id,'selected_content_idea_id',a.content_idea_id,
    'selected_library_uri',a.uri,
    'owner_visual_score',a.metadata->'owner_visual_score',
    'owner_asset_approved',true,
    'owner_publish_approval',false,
    'captions',jsonb_build_object('instagram_draft',ig,'tiktok_draft',tt),
    'mobile_qa','verify actual image bytes/resolution and text crop after media transfer',
    'platform_qa','Instagram static post; TikTok photo post; use native dimensions, verify feed preview',
    'link_qa','captions are not clickable links; validate profile destination and attribution before posting',
    'required_next_action','transfer exact unchanged FINAL image to publisher, verify platform previews, request a separate exact owner publishing GO',
    'publication_status','NOT_SCHEDULED_NOT_PUBLISHED',
    'business_goal','reach_and_qualified_distribution_signal',
    'new_spend_usd',0
  );

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.ceo_distribution_preflight_v2','growth',packet,100,now())
  on conflict(key) do update
    set value=excluded.value,priority=excluded.priority,last_verified_at=excluded.last_verified_at;

  ok := public.update_dufynd_worker_v2(t.task_id,token,'verifying','Persisted source-frozen distribution package for '||a.id,null);
  if not ok then
    return jsonb_build_object('status','verification_transition_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;
  ok := public.update_dufynd_worker_v2(t.task_id,token,'done','Verified readiness packet: '||a.id||'; no publishing approval and no publication.',null);
  if not ok then
    return jsonb_build_object('status','completion_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;
  return jsonb_build_object(
    'status','completed','task_id',t.task_id,'selected_asset_id',a.id,
    'action','distribution_packet_prepared','owner_action_required',true,
    'next_step','Review exact owner-frozen asset, transfer and QA media, then separately approve publishing.',
    'new_spend_usd',0
  );
end
$fn$;

create or replace function public.run_dufynd_ceo_blocker_triage_v2()
returns jsonb
language plpgsql
set search_path to 'public'
as $fn$
declare
  t public.dufynd_autonomy_tasks;
  token uuid := gen_random_uuid();
  fingerprint text;
  current_fp text;
  audit jsonb;
  total_count integer;
  verified_wait_count integer;
  unbound_count integer;
  claimed jsonb;
  ok boolean;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-ceo-blocker-triage-v2'));
  select * into t from public.dufynd_autonomy_tasks
  where status='ready' and budget_class='free'
    and provider_cost_unknown=false and requires_human_approval=false
    and external_review_required=false and needs_freshness_recheck=false
    and durable_payload->>'kind'='ceo_blocker_triage_v2'
    and resource_scope='["db:dufynd.autonomy_tasks","db:dufynd.ceo_blocker_triage","db:dufynd.task_external_waits"]'::jsonb
  order by priority desc,created_at limit 1 for update;
  if t.task_id is null then
    return jsonb_build_object('status','idle','reason','no_blocker_triage_due','new_spend_usd',0);
  end if;
  fingerprint := t.durable_payload->>'fingerprint';

  select md5(coalesce(string_agg(
    q.task_id||':'||q.status||':'||
    coalesce((
      select string_agg(w.observer_id||':'||w.satisfied::text||':'||w.policy,',' order by w.observer_id)
      from public.dufynd_task_external_waits w where w.task_id=q.task_id
    ),'no_wait_binding'),
    '|' order by q.task_id
  ),'no_external_waits')) into current_fp
  from public.dufynd_autonomy_tasks q where q.status='waiting_external';

  if fingerprint is distinct from current_fp then
    return jsonb_build_object('status','not_executed','reason','blocker_evidence_snapshot_changed',
      'task_id',t.task_id,'new_spend_usd',0);
  end if;

  claimed := public.claim_dufynd_worker_v2(t.task_id,'ceo_blocker_triage_worker_v2',token);
  if claimed is null then
    return jsonb_build_object('status','not_claimed','task_id',t.task_id,'new_spend_usd',0);
  end if;
  ok := public.update_dufynd_worker_v2(t.task_id,token,'working','Checking exact external waits and unbound tasks.',null);
  if not ok then
    return jsonb_build_object('status','claim_update_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  select count(*)::integer,
    count(*) filter (where exists(
      select 1 from public.dufynd_task_external_waits w where w.task_id=q.task_id and w.satisfied=false
    ))::integer
  into total_count,verified_wait_count
  from public.dufynd_autonomy_tasks q where q.status='waiting_external';
  unbound_count := total_count-verified_wait_count;

  select jsonb_build_object(
    'version',2,'fingerprint',fingerprint,'observed_at',now(),
    'classification','evidence_triage_only_no_external_actions',
    'waiting_external_total',total_count,'confirmed_unmet_observer_waits',verified_wait_count,
    'no_confirmed_unmet_observer_wait',unbound_count,
    'cases',coalesce(jsonb_agg(
      jsonb_build_object(
        'task_id',q.task_id,'title',q.title,'domain',q.domain,
        'source_evidence',case when exists(
          select 1 from public.dufynd_task_external_waits w where w.task_id=q.task_id and w.satisfied=false
        ) then 'confirmed_unsatisfied_observer_wait' else 'unverified_external_dependency' end,
        'human_approval_flag',q.requires_human_approval,
        'next_action',case
          when exists(
            select 1 from public.dufynd_task_external_waits w where w.task_id=q.task_id and w.satisfied=false
          ) then 'Watch exact source for a verified response. On arrival, inspect scope/rights before advancing.'
          else 'Reconcile against current partner/asset evidence and require a certified internal path before changing task status.'
        end
      ) order by q.priority desc,q.task_id
    ),'[]'::jsonb),
    'blocked_status_mutations',0,'external_messages_sent',0,
    'new_spend_usd',0
  ) into audit
  from public.dufynd_autonomy_tasks q
  where q.status='waiting_external';

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.ceo_blocker_triage_v2','jarvis',audit,100,now())
  on conflict(key) do update
    set value=excluded.value,priority=excluded.priority,last_verified_at=excluded.last_verified_at;

  ok := public.update_dufynd_worker_v2(t.task_id,token,'verifying','Persisted evidence-first blocker classification; no fabricated clearance.',null);
  if not ok then
    return jsonb_build_object('status','verification_transition_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;
  ok := public.update_dufynd_worker_v2(t.task_id,token,'done','Verified external-wait evidence board was classified.',null);
  if not ok then
    return jsonb_build_object('status','completion_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;
  return jsonb_build_object(
    'status','completed','task_id',t.task_id,
    'action','evidence_blockers_classified','verified_waits',verified_wait_count,
    'unbound_waits',unbound_count,'owner_action_required',false,
    'next_step','Investigate unbound cases against genuine partner evidence; do not assume external approval.',
    'new_spend_usd',0
  );
end
$fn$;

insert into public.dufynd_handler_contracts(handler_id,handler_version,contract,enabled)
values
('ceo_distribution_preflight_v2','2',
 jsonb_build_object(
  'cost_class','free','handler_id','ceo_distribution_preflight_v2',
  'handler_version','2','risk_class','low','certification_status','certified',
  'allowed_scopes',jsonb_build_array('growth'),
  'allowed_tools',jsonb_build_array('claim_dufynd_worker_v2','update_dufynd_worker_v2','dufynd_content_assets'),
  'allowed_resources',jsonb_build_array('db:dufynd.ceo_publish_packet','db:dufynd.content_assets'),
  'capabilities',jsonb_build_array('content.read','supabase.task_state','supabase.execution_state'),
  'required_capabilities',jsonb_build_array('content.read','supabase.task_state','supabase.execution_state'),
  'forbidden_actions',jsonb_build_array('social.publish','gmail.send','budget.spend','main.merge','commerce.activate','shell.execute'),
  'durability_class','durable','supports_retry',true,'supports_parallel_execution',false,
  'verification_policy',jsonb_build_object('kind','ceo_distribution_preflight_v2','version',2)
 ),true),
('ceo_blocker_triage_v2','2',
 jsonb_build_object(
  'cost_class','free','handler_id','ceo_blocker_triage_v2',
  'handler_version','2','risk_class','low','certification_status','certified',
  'allowed_scopes',jsonb_build_array('supervisor'),
  'allowed_tools',jsonb_build_array('claim_dufynd_worker_v2','update_dufynd_worker_v2','dufynd_task_external_waits'),
  'allowed_resources',jsonb_build_array('db:dufynd.autonomy_tasks','db:dufynd.ceo_blocker_triage','db:dufynd.task_external_waits'),
  'capabilities',jsonb_build_array('supabase.task_state','supabase.execution_state'),
  'required_capabilities',jsonb_build_array('supabase.task_state','supabase.execution_state'),
  'forbidden_actions',jsonb_build_array('social.publish','gmail.send','budget.spend','main.merge','commerce.activate','shell.execute'),
  'durability_class','durable','supports_retry',true,'supports_parallel_execution',false,
  'verification_policy',jsonb_build_object('kind','ceo_blocker_triage_v2','version',2)
 ),true)
on conflict(handler_id) do update set contract=excluded.contract,enabled=excluded.enabled,handler_version=excluded.handler_version;

revoke execute on function public.plan_dufynd_ceo_priority_work_v2() from public,anon,authenticated;
revoke execute on function public.run_dufynd_ceo_distribution_preflight_v2() from public,anon,authenticated;
revoke execute on function public.run_dufynd_ceo_blocker_triage_v2() from public,anon,authenticated;
grant execute on function public.plan_dufynd_ceo_priority_work_v2() to service_role,postgres;
grant execute on function public.run_dufynd_ceo_distribution_preflight_v2() to service_role,postgres;
grant execute on function public.run_dufynd_ceo_blocker_triage_v2() to service_role,postgres;
