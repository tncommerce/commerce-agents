-- Jarvis V4.8: turn the top zero-budget idea into a concrete production packet.
-- Deterministic planning only: no generation, publishing, outreach, model calls or spend.

create or replace function public.read_dufynd_content_production_packet_v1()
returns jsonb
language sql
stable
set search_path to 'public'
as $function$
with q as (
  select value from public.dufynd_master_status
  where key='jarvis.zero_budget_content_queue_v1'
),
top_pick as (
  select value->'next_content_move' as pick from q
),
idea as (
  select i.*
  from public.dufynd_content_ideas i, top_pick p
  where i.id=p.pick->>'idea_id'
  limit 1
)
select jsonb_build_object(
  'version',1,
  'observed_at',now(),
  'source_queue','jarvis.zero_budget_content_queue_v1',
  'idea_id',i.id,
  'content_id','zb_'||i.id||'_'||to_char(now() at time zone 'UTC','YYYYMMDD'),
  'title',i.title,
  'format_id',i.format_id,
  'hook',i.hook,
  'concept',i.concept,
  'objective',i.objective,
  'affiliate_role',i.affiliate_role,
  'production_mode','zero_budget',
  'visual_direction',case
    when i.format_id='static_text_hook' then jsonb_build_array(
      'platform_native_single_message',
      'strong_typographic_hierarchy',
      'one_immediate_visual_event_or_relatable_context',
      'avoid_generic_black_gold_luxury_ad',
      'mobile_first_safe_zones'
    )
    when i.format_id='static_educational_carousel' then jsonb_build_array(
      'slide_1_scroll_stop_claim_or_question',
      'one_point_per_slide',
      'visual_language_changes_enough_to_avoid_template_fatigue',
      'saveable_mobile_first'
    )
    when i.id='idea_ref29_screenproof_001' then jsonb_build_array(
      'real_dufynd_screen_only',
      'show_real_problem_then_real_product_proof',
      'no_fabricated_ui_or_result'
    )
    else jsonb_build_array(
      'platform_native',
      'clear_scroll_stop',
      'avoid_template_ad_feel',
      'fresh_visual_qa_required'
    )
  end,
  'copy_structure',jsonb_build_object(
    'opening',i.hook,
    'body_rule','Support the premise with one concrete, truthful point; do not over-explain.',
    'cta_rule',case
      when coalesce(i.objective,'') like '%engagement%' then 'Use one simple opinion question that invites disagreement or examples.'
      when coalesce(i.objective,'') like '%save%' then 'End with one save-worthy takeaway.'
      else 'Use one low-friction comment or save prompt only if it naturally fits.'
    end
  ),
  'hard_gates',(select value->'hard_pauses' from public.dufynd_master_status where key='content.zero_budget_policy.20261006'),
  'qa',jsonb_build_object(
    'fresh_visual_recheck_required',true,
    'target_score',9.5,
    'scroll_stop_question','Would a person who does not know DUFYND stop for this?',
    'reject_if_template_ad',true,
    'reject_if_hard_gate_conflict',true,
    'reject_if_unsupported_claim',true,
    'reject_if_product_identity_drifts',true
  ),
  'risk_notes',coalesce(i.risk_notes,'[]'::jsonb),
  'paid_generation_allowed',false,
  'publishing_allowed',false,
  'next_step','create_or_select_visual_then_run_fresh_creative_qa',
  'new_spend_usd',0
)
from idea i;
$function$;

revoke execute on function public.read_dufynd_content_production_packet_v1() from public, anon, authenticated;
grant execute on function public.read_dufynd_content_production_packet_v1() to service_role, postgres;

insert into public.dufynd_handler_contracts(handler_id,handler_version,contract,enabled)
values(
  'content_production_packet','1',
  jsonb_build_object(
    'handler_id','content_production_packet',
    'handler_version','1',
    'certification_status','certified',
    'risk_class','low',
    'cost_class','free',
    'durability_class','durable',
    'capabilities',jsonb_build_array('content.read','supabase.task_state','supabase.execution_state'),
    'required_capabilities',jsonb_build_array('content.read','supabase.task_state','supabase.execution_state'),
    'forbidden_actions',jsonb_build_array('gmail.send','social.publish','budget.spend','main.merge','commerce.activate','shell.execute'),
    'allowed_scopes',jsonb_build_array('content'),
    'allowed_resources',jsonb_build_array('db:dufynd.content_ideas','db:dufynd.zero_budget_queue','db:dufynd.content_packet'),
    'allowed_tools',jsonb_build_array('read_dufynd_content_production_packet_v1','claim_dufynd_worker_v2','update_dufynd_worker_v2'),
    'verification_policy',jsonb_build_object('kind','content_production_packet','version',1),
    'supports_retry',true,
    'supports_parallel_execution',false,
    'required_approval_class',null
  ),
  true
)
on conflict(handler_id,handler_version) do update
set contract=excluded.contract,enabled=excluded.enabled;

create or replace function public.plan_dufynd_content_packet_work_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  q jsonb;
  idea_id text;
  tid text;
  created boolean := false;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-content-packet-planner-v1'));
  q := public.get_dufynd_next_autonomous_action();
  if q->>'state' in ('work_available','work_in_progress','owner_gate') then
    return jsonb_build_object('version',1,'state',q->>'state','created',false,'paid_calls',0,'new_spend_usd',0);
  end if;

  select value#>>'{next_content_move,idea_id}' into idea_id
  from public.dufynd_master_status
  where key='jarvis.zero_budget_content_queue_v1';

  if idea_id is null then
    return jsonb_build_object('version',1,'state','no_ranked_content_candidate','created',false,'paid_calls',0,'new_spend_usd',0);
  end if;

  tid := 'bizplan:content-packet:'||idea_id||':'||to_char(now() at time zone 'UTC','YYYYMMDD');

  if not exists(
    select 1 from public.dufynd_autonomy_tasks where task_id=tid and status='done'
  ) then
    insert into public.dufynd_autonomy_tasks(
      task_id,domain,title,instruction,status,priority,budget_class,
      resource_scope,durability_policy,durable_payload,required_capabilities,forbidden_actions
    ) values(
      tid,'content','Prepare zero-budget production packet',
      'Turn the current highest-ranked zero-budget DUFYND content idea into a concrete production packet with hook, visual direction, copy structure and QA gates. Do not generate or publish media.',
      'ready',93,'free',
      '["db:dufynd.content_ideas","db:dufynd.zero_budget_queue","db:dufynd.content_packet"]'::jsonb,
      'durable',
      jsonb_build_object('kind','content_production_packet','version',1,'idea_id',idea_id),
      '["content.read","supabase.task_state","supabase.execution_state"]'::jsonb,
      '["gmail.send","social.publish","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
    ) on conflict(task_id) do nothing;
    created := found;
  end if;

  return jsonb_build_object(
    'version',1,'state',case when created then 'work_planned' else 'no_content_packet_work_due' end,
    'created',created,'task_id',case when created then tid else null end,
    'idea_id',idea_id,'paid_calls',0,'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.plan_dufynd_content_packet_work_v1() from public, anon, authenticated;
grant execute on function public.plan_dufynd_content_packet_work_v1() to service_role, postgres;

create or replace function public.run_dufynd_content_packet_worker_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  t public.dufynd_autonomy_tasks;
  token uuid := gen_random_uuid();
  claimed jsonb;
  packet jsonb;
  evidence text;
  ok boolean;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-content-packet-worker-v1'));

  select q.* into t
  from public.dufynd_autonomy_tasks q
  where q.status='ready'
    and q.domain='content'
    and q.budget_class='free'
    and not q.provider_cost_unknown
    and not q.requires_human_approval
    and not q.external_review_required
    and not q.needs_freshness_recheck
    and q.durable_payload->>'kind'='content_production_packet'
    and q.resource_scope='["db:dufynd.content_ideas","db:dufynd.zero_budget_queue","db:dufynd.content_packet"]'::jsonb
    and public.dufynd_capability_list_valid(q.required_capabilities)
    and public.dufynd_capability_list_valid(q.forbidden_actions)
  order by q.priority desc,q.created_at,q.task_id
  limit 1
  for update;

  if t.task_id is null then
    return jsonb_build_object('version',1,'status','idle','reason','no_content_packet_task','new_spend_usd',0);
  end if;

  claimed := public.claim_dufynd_worker_v2(t.task_id,'content_packet_worker_v1',token);
  if claimed is null then
    return jsonb_build_object('version',1,'status','not_claimed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  ok := public.update_dufynd_worker_v2(t.task_id,token,'working','Preparing deterministic zero-budget production packet.',null);
  if not ok then
    return jsonb_build_object('version',1,'status','claim_update_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  packet := public.read_dufynd_content_production_packet_v1();
  if packet is null or packet->>'idea_id' is null then
    ok := public.update_dufynd_worker_v2(t.task_id,token,'blocked','No ranked zero-budget candidate available.',null);
    return jsonb_build_object('version',1,'status','blocked','task_id',t.task_id,'new_spend_usd',0);
  end if;

  evidence := 'Zero-budget production packet: '||packet::text;

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.content_production_packet_v1','content',packet,93,now())
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

  return jsonb_build_object('version',1,'status','completed','task_id',t.task_id,'packet',packet,'new_spend_usd',0);
end;
$function$;

revoke execute on function public.run_dufynd_content_packet_worker_v1() from public, anon, authenticated;
grant execute on function public.run_dufynd_content_packet_worker_v1() to service_role, postgres;

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
  content_plan jsonb;
  packet_plan jsonb;
  business_plan jsonb;
  report jsonb;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-free-planner-v1'));
  before_state := public.get_dufynd_next_autonomous_action();

  if before_state->>'state' in ('work_available','work_in_progress','owner_gate') then
    report := jsonb_build_object(
      'version',5,'observed_at',now(),'state',before_state->>'state',
      'action','none','reason','existing_work_or_gate_already_explains_next_step',
      'queue',before_state,'paid_calls',0,'new_spend_usd',0
    );
  else
    wake_result := public.wake_dufynd_purchase_freshness();
    after_state := public.get_dufynd_next_autonomous_action();

    if after_state->>'state'='work_available' then
      report := jsonb_build_object(
        'version',5,'observed_at',now(),'state','work_replenished',
        'action','purchase_freshness_wake','wake_result',wake_result,
        'queue',after_state,'paid_calls',0,'new_spend_usd',0
      );
    else
      affiliate_plan := public.plan_dufynd_affiliate_work_v1();
      after_state := public.get_dufynd_next_autonomous_action();

      if after_state->>'state'='work_available' then
        report := jsonb_build_object(
          'version',5,'observed_at',now(),'state','work_replenished',
          'action','affiliate_evidence_planning','affiliate_plan',affiliate_plan,
          'queue',after_state,'paid_calls',0,'new_spend_usd',0
        );
      else
        content_plan := public.plan_dufynd_zero_budget_content_work_v1();
        after_state := public.get_dufynd_next_autonomous_action();

        if after_state->>'state'='work_available' then
          report := jsonb_build_object(
            'version',5,'observed_at',now(),'state','work_replenished',
            'action','zero_budget_content_planning','content_plan',content_plan,
            'queue',after_state,'paid_calls',0,'new_spend_usd',0
          );
        else
          packet_plan := public.plan_dufynd_content_packet_work_v1();
          after_state := public.get_dufynd_next_autonomous_action();

          if after_state->>'state'='work_available' then
            report := jsonb_build_object(
              'version',5,'observed_at',now(),'state','work_replenished',
              'action','content_packet_planning','content_plan',content_plan,'packet_plan',packet_plan,
              'queue',after_state,'paid_calls',0,'new_spend_usd',0
            );
          else
            business_plan := public.plan_dufynd_autonomous_business_work_v1();
            after_state := public.get_dufynd_next_autonomous_action();
            report := jsonb_build_object(
              'version',5,'observed_at',now(),
              'state',case when after_state->>'state'='work_available' then 'work_replenished' else coalesce(business_plan->>'state','planner_gap') end,
              'action','autonomous_business_planning','wake_result',wake_result,
              'affiliate_plan',affiliate_plan,'content_plan',content_plan,'packet_plan',packet_plan,
              'business_plan',business_plan,'queue',after_state,
              'business_next_move',business_plan->>'business_next_move',
              'master_action_required',false,'waiting_external_is_global_blocker',false,
              'paid_calls',0,'new_spend_usd',0
            );
          end if;
        end if;
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
  where jobname='dufynd-content-packet-worker-v1'
  order by jobid desc limit 1;
  if existing_job is not null then perform cron.unschedule(existing_job); end if;
  perform cron.schedule(
    'dufynd-content-packet-worker-v1',
    '*/2 * * * *',
    'select public.run_dufynd_content_packet_worker_v1();'
  );
end
$$;

select public.plan_dufynd_free_work_v1();
select public.run_dufynd_content_packet_worker_v1();
