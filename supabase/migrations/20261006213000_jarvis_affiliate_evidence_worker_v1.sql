-- Jarvis V4.6: reconcile verified affiliate evidence into the operating registry.
-- Internal, deterministic, zero-spend. Does not send mail, activate commerce, publish, or change tracking readiness.

insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
values(
  'affiliate.evidence.top_parfuemerie.20261006',
  'affiliate',
  jsonb_build_object(
    'merchant_id','top-parfuemerie',
    'evidence_date','2026-10-06',
    'source','direct_merchant_email',
    'thread_id','1a0f3ec67edd1ee0',
    'feed_regularly_updated',true,
    'feed_contains_in_stock_only',true,
    'feed_prices_current',true,
    'feed_images_current',true,
    'feed_image_rights_confirmed',true,
    'rights_scope','dufynd_integration_affiliate_program_context_only',
    'purchase_destination','top_parfuemerie_online_shop',
    'tracking_verified',false,
    'safe_interpretation','Feed truth is confirmed; tracking remains a separate unresolved requirement.'
  ),
  100,
  now()
)
on conflict(key) do update
set value=excluded.value,priority=excluded.priority,last_verified_at=excluded.last_verified_at;

create or replace function public.read_dufynd_affiliate_readiness_v1()
returns jsonb
language sql
stable
set search_path to 'public'
as $function$
with p as (
  select * from public.dufynd_affiliate_partners where merchant_id='top-parfuemerie'
), e as (
  select value,last_verified_at from public.dufynd_master_status
  where key='affiliate.evidence.top_parfuemerie.20261006'
)
select jsonb_build_object(
  'version',1,
  'observed_at',now(),
  'merchant_id','top-parfuemerie',
  'status',(select status from p),
  'feed_ready',(select feed_ready from p),
  'tracking_ready',(select tracking_ready from p),
  'evidence_present',exists(select 1 from e),
  'feed_truth_confirmed',coalesce((select (value->>'feed_regularly_updated')::boolean from e),false)
    and coalesce((select (value->>'feed_contains_in_stock_only')::boolean from e),false),
  'image_rights_scope',coalesce((select value->>'rights_scope' from e),'unknown'),
  'tracking_verified',coalesce((select (value->>'tracking_verified')::boolean from e),false),
  'next_revenue_blocker',case
    when not coalesce((select feed_ready from p),false) then 'feed_truth'
    when not coalesce((select tracking_ready from p),false) then 'verify_tracked_product_clickout'
    else 'exact_sku_offer_activation'
  end,
  'new_spend_usd',0
);
$function$;

revoke execute on function public.read_dufynd_affiliate_readiness_v1() from public, anon, authenticated;
grant execute on function public.read_dufynd_affiliate_readiness_v1() to service_role, postgres;

insert into public.dufynd_handler_contracts(handler_id,handler_version,contract,enabled)
values(
  'affiliate_evidence_reconcile','1',
  jsonb_build_object(
    'handler_id','affiliate_evidence_reconcile',
    'handler_version','1',
    'certification_status','certified',
    'risk_class','low',
    'cost_class','free',
    'durability_class','durable',
    'capabilities',jsonb_build_array('commerce.read','commerce.evidence.write','supabase.task_state','supabase.execution_state'),
    'required_capabilities',jsonb_build_array('commerce.read','commerce.evidence.write','supabase.task_state','supabase.execution_state'),
    'forbidden_actions',jsonb_build_array('gmail.send','social.publish','budget.spend','main.merge','commerce.activate','shell.execute'),
    'allowed_scopes',jsonb_build_array('commerce'),
    'allowed_resources',jsonb_build_array('db:dufynd.affiliate_partners','db:dufynd.affiliate_evidence'),
    'allowed_tools',jsonb_build_array('read_dufynd_affiliate_readiness_v1','claim_dufynd_worker_v2','update_dufynd_worker_v2'),
    'verification_policy',jsonb_build_object('kind','affiliate_evidence_reconcile','version',1),
    'supports_retry',true,
    'supports_parallel_execution',false,
    'required_approval_class',null
  ),
  true
)
on conflict(handler_id,handler_version) do update
set contract=excluded.contract,enabled=excluded.enabled;

create or replace function public.plan_dufynd_affiliate_work_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  q jsonb;
  tid text := 'bizplan:affiliate-evidence:top-parfuemerie:20261006';
  created boolean := false;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-affiliate-planner-v1'));
  q := public.get_dufynd_next_autonomous_action();
  if q->>'state' in ('work_available','work_in_progress','owner_gate') then
    return jsonb_build_object('version',1,'state',q->>'state','created',false,'paid_calls',0,'new_spend_usd',0);
  end if;

  if exists(select 1 from public.dufynd_master_status where key='affiliate.evidence.top_parfuemerie.20261006')
     and exists(
       select 1 from public.dufynd_affiliate_partners
       where merchant_id='top-parfuemerie'
         and notes not like '%MERCHANT-EVIDENCE-20261006%'
     ) then
    insert into public.dufynd_autonomy_tasks(
      task_id,domain,title,instruction,status,priority,budget_class,
      resource_scope,durability_policy,durable_payload,required_capabilities,forbidden_actions
    ) values(
      tid,'commerce','Reconcile top Parfümerie merchant evidence',
      'Reconcile the already-verified 2026-10-06 merchant feed evidence into the internal affiliate registry. Preserve tracking_ready=false until a tracked clickout is separately verified.',
      'ready',98,'free',
      '["db:dufynd.affiliate_partners","db:dufynd.affiliate_evidence"]'::jsonb,
      'durable',
      '{"kind":"affiliate_evidence_reconcile","merchant_id":"top-parfuemerie","evidence_key":"affiliate.evidence.top_parfuemerie.20261006"}'::jsonb,
      '["commerce.read","commerce.evidence.write","supabase.task_state","supabase.execution_state"]'::jsonb,
      '["gmail.send","social.publish","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
    ) on conflict(task_id) do nothing;
    created := found;
  end if;

  return jsonb_build_object(
    'version',1,
    'state',case when created then 'work_planned' else 'no_affiliate_reconciliation_due' end,
    'created',created,
    'task_id',case when created then tid else null end,
    'paid_calls',0,
    'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.plan_dufynd_affiliate_work_v1() from public, anon, authenticated;
grant execute on function public.plan_dufynd_affiliate_work_v1() to service_role, postgres;

create or replace function public.run_dufynd_affiliate_worker_v1()
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
  perform pg_advisory_xact_lock(hashtext('dufynd-affiliate-worker-v1'));

  select q.* into t
  from public.dufynd_autonomy_tasks q
  where q.status='ready'
    and q.domain='commerce'
    and q.budget_class='free'
    and not q.provider_cost_unknown
    and not q.requires_human_approval
    and not q.external_review_required
    and not q.needs_freshness_recheck
    and q.durable_payload->>'kind'='affiliate_evidence_reconcile'
    and q.durable_payload->>'merchant_id'='top-parfuemerie'
    and q.resource_scope='["db:dufynd.affiliate_partners","db:dufynd.affiliate_evidence"]'::jsonb
    and public.dufynd_capability_list_valid(q.required_capabilities)
    and public.dufynd_capability_list_valid(q.forbidden_actions)
  order by q.priority desc,q.created_at,q.task_id
  limit 1
  for update;

  if t.task_id is null then
    return jsonb_build_object('version',1,'status','idle','reason','no_affiliate_reconcile_task','new_spend_usd',0);
  end if;

  claimed := public.claim_dufynd_worker_v2(t.task_id,'affiliate_evidence_worker_v1',token);
  if claimed is null then
    return jsonb_build_object('version',1,'status','not_claimed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  ok := public.update_dufynd_worker_v2(t.task_id,token,'working','Reconciling verified merchant evidence.',null);
  if not ok then
    return jsonb_build_object('version',1,'status','claim_update_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  perform set_config('dufynd.worker_write',token::text,true);
  update public.dufynd_affiliate_partners
  set
    feed_ready=true,
    notes=case
      when notes like '%MERCHANT-EVIDENCE-20261006%' then notes
      else notes || E'\nMERCHANT-EVIDENCE-20261006: Direct merchant email confirmed the Awin feed is regularly updated, contains only in-stock articles, and supplies current prices/images. Merchant confirmed suitable image rights for DUFYND integration / affiliate-program context. Purchases conclude in the top Parfümerie online shop. This does NOT verify a tracked clickout and does NOT grant blanket social-ad image rights.'
    end,
    updated_at=now()
  where merchant_id='top-parfuemerie';
  perform set_config('dufynd.worker_write','',true);

  audit := public.read_dufynd_affiliate_readiness_v1();
  evidence := 'Deterministic affiliate evidence reconciliation: '||audit::text;

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.affiliate_readiness_v1','affiliate',audit,98,now())
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

  return jsonb_build_object('version',1,'status','completed','task_id',t.task_id,'audit',audit,'new_spend_usd',0);
end;
$function$;

revoke execute on function public.run_dufynd_affiliate_worker_v1() from public, anon, authenticated;
grant execute on function public.run_dufynd_affiliate_worker_v1() to service_role, postgres;

create or replace function public.plan_dufynd_free_work_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  before_state jsonb;
  after_state jsonb;
  wake_result jsonb;
  affiliate_plan jsonb;
  business_plan jsonb;
  report jsonb;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-free-planner-v1'));
  before_state := public.get_dufynd_next_autonomous_action();

  if before_state->>'state' in ('work_available','work_in_progress','owner_gate') then
    report := jsonb_build_object(
      'version',3,'observed_at',now(),'state',before_state->>'state',
      'action','none','reason','existing_work_or_gate_already_explains_next_step',
      'queue',before_state,'paid_calls',0,'new_spend_usd',0
    );
  else
    wake_result := public.wake_dufynd_purchase_freshness();
    after_state := public.get_dufynd_next_autonomous_action();

    if after_state->>'state'='work_available' then
      report := jsonb_build_object(
        'version',3,'observed_at',now(),'state','work_replenished',
        'action','purchase_freshness_wake','wake_result',wake_result,
        'queue',after_state,'paid_calls',0,'new_spend_usd',0
      );
    else
      affiliate_plan := public.plan_dufynd_affiliate_work_v1();
      after_state := public.get_dufynd_next_autonomous_action();

      if after_state->>'state'='work_available' then
        report := jsonb_build_object(
          'version',3,'observed_at',now(),'state','work_replenished',
          'action','affiliate_evidence_planning','affiliate_plan',affiliate_plan,
          'queue',after_state,'paid_calls',0,'new_spend_usd',0
        );
      else
        business_plan := public.plan_dufynd_autonomous_business_work_v1();
        after_state := public.get_dufynd_next_autonomous_action();
        report := jsonb_build_object(
          'version',3,'observed_at',now(),
          'state',case when after_state->>'state'='work_available' then 'work_replenished' else coalesce(business_plan->>'state','planner_gap') end,
          'action','autonomous_business_planning','wake_result',wake_result,
          'affiliate_plan',affiliate_plan,'business_plan',business_plan,'queue',after_state,
          'business_next_move',business_plan->>'business_next_move',
          'master_action_required',false,'waiting_external_is_global_blocker',false,
          'paid_calls',0,'new_spend_usd',0
        );
      end if;
    end if;
  end if;

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.planner_v1','jarvis',report,100,now())
  on conflict(key) do update
  set value=excluded.value,priority=excluded.priority,last_verified_at=excluded.last_verified_at;

  return report;
end;
$function$;

do $$
declare existing_job bigint;
begin
  select jobid into existing_job from cron.job
  where jobname='dufynd-affiliate-evidence-worker-v1'
  order by jobid desc limit 1;
  if existing_job is not null then perform cron.unschedule(existing_job); end if;
  perform cron.schedule(
    'dufynd-affiliate-evidence-worker-v1',
    '*/2 * * * *',
    'select public.run_dufynd_affiliate_worker_v1();'
  );
end
$$;

select public.plan_dufynd_free_work_v1();
select public.run_dufynd_affiliate_worker_v1();
