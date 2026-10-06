-- Jarvis V4.7: persist current DUFYND zero-budget content policy and build a daily production shortlist.
-- No media generation, no publishing, no model calls, no spend.

insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
values(
  'content.zero_budget_policy.20261006',
  'creative',
  jsonb_build_object(
    'version',1,
    'effective_from','2026-10-06',
    'budget_mode','zero_budget_until_2026_12_01',
    'north_star','reach_then_qualified_traffic_then_revenue',
    'fresh_visual_recheck_required',true,
    'publication_quality_target',9.5,
    'hard_pauses',jsonb_build_array(
      'animals_cozy_bed_sofa',
      'cologne_dom_station',
      'recurring_hero_male',
      'split_screen_before_after',
      'same_person_different_scent',
      'mood_energy_stress_focus_effect_claims'
    ),
    'preferred_zero_budget',jsonb_build_array(
      'relatable_static_meme',
      'carousel',
      'screenshot_chat',
      'graphic_poster',
      'editorial_static',
      'existing_short_recut',
      'real_dufynd_screen_proof'
    ),
    'paid_generation_requires_owner_go',true,
    'tinyfish_requires_owner_go_each_use',true
  ),
  100,
  now()
)
on conflict(key) do update
set value=excluded.value,priority=excluded.priority,last_verified_at=excluded.last_verified_at;

create or replace function public.read_dufynd_zero_budget_content_queue_v1()
returns jsonb
language sql
stable
set search_path to 'public'
as $function$
with classified as (
  select
    i.id,
    i.title,
    i.format_id,
    i.fragrance,
    i.hook,
    i.objective,
    i.affiliate_role,
    i.priority,
    case
      when i.id in ('idea_persona_shift_001','idea_season_switch_001')
        then 'hard_pause'
      when i.id in (
        'idea_fragrance_genesis_001','idea_genesis_002',
        'idea_action_scent_001','idea_adrenaline_reveal_001',
        'idea_exploded_bottle_001'
      ) then 'hold_paid_generation'
      when i.format_id in ('static_text_hook','static_educational_carousel','static_recommendation','static_premium_editorial','static_scent_mood')
        or i.id='idea_ref29_screenproof_001'
        then 'now'
      else 'watch'
    end as lane,
    i.priority
      + case
          when coalesce(i.objective,'') like '%engagement%' then 25
          when i.format_id='static_text_hook' then 20
          when i.id='idea_ref29_screenproof_001' then 18
          when i.format_id='static_educational_carousel' then 12
          when i.format_id='static_recommendation' then 8
          when i.format_id in ('static_premium_editorial','static_scent_mood') then 5
          else 0
        end as zero_budget_score
  from public.dufynd_content_ideas i
  where i.status='planned'
),
now_rows as (
  select * from classified where lane='now'
  order by zero_budget_score desc,priority desc,id limit 12
),
pause_rows as (
  select * from classified where lane='hard_pause'
  order by priority desc,id
),
hold_rows as (
  select * from classified where lane='hold_paid_generation'
  order by priority desc,id
),
watch_rows as (
  select * from classified where lane='watch'
  order by zero_budget_score desc,priority desc,id limit 12
)
select jsonb_build_object(
  'version',1,
  'observed_at',now(),
  'policy_key','content.zero_budget_policy.20261006',
  'decision','zero_budget_queue_ready',
  'now_count',(select count(*) from now_rows),
  'hard_pause_count',(select count(*) from pause_rows),
  'hold_paid_generation_count',(select count(*) from hold_rows),
  'next_content_move',(
    select jsonb_build_object(
      'idea_id',id,'title',title,'format_id',format_id,'hook',hook,
      'objective',objective,'zero_budget_score',zero_budget_score,
      'reason','highest_scoring_zero_budget_candidate_requires_fresh_creative_qa'
    ) from now_rows limit 1
  ),
  'now',coalesce((
    select jsonb_agg(jsonb_build_object(
      'idea_id',id,'title',title,'format_id',format_id,'fragrance',fragrance,
      'hook',hook,'objective',objective,'affiliate_role',affiliate_role,
      'priority',priority,'zero_budget_score',zero_budget_score
    ) order by zero_budget_score desc,priority desc,id)
    from now_rows
  ),'[]'::jsonb),
  'hard_pause',coalesce((
    select jsonb_agg(jsonb_build_object(
      'idea_id',id,'title',title,'reason','conflicts_with_current_owner_creative_gate'
    ) order by priority desc,id) from pause_rows
  ),'[]'::jsonb),
  'hold_paid_generation',coalesce((
    select jsonb_agg(jsonb_build_object(
      'idea_id',id,'title',title,'reason','requires_high_quality_generation_or_assets_not_justified_in_zero_budget_mode'
    ) order by priority desc,id) from hold_rows
  ),'[]'::jsonb),
  'watch',coalesce((
    select jsonb_agg(jsonb_build_object(
      'idea_id',id,'title',title,'format_id',format_id,'hook',hook,'zero_budget_score',zero_budget_score
    ) order by zero_budget_score desc,priority desc,id) from watch_rows
  ),'[]'::jsonb),
  'publishing_allowed',false,
  'new_spend_usd',0
);
$function$;

revoke execute on function public.read_dufynd_zero_budget_content_queue_v1() from public, anon, authenticated;
grant execute on function public.read_dufynd_zero_budget_content_queue_v1() to service_role, postgres;

insert into public.dufynd_handler_contracts(handler_id,handler_version,contract,enabled)
values(
  'content_backlog_prioritize','1',
  jsonb_build_object(
    'handler_id','content_backlog_prioritize',
    'handler_version','1',
    'certification_status','certified',
    'risk_class','low',
    'cost_class','free',
    'durability_class','durable',
    'capabilities',jsonb_build_array('content.read','supabase.task_state','supabase.execution_state'),
    'required_capabilities',jsonb_build_array('content.read','supabase.task_state','supabase.execution_state'),
    'forbidden_actions',jsonb_build_array('gmail.send','social.publish','budget.spend','main.merge','commerce.activate','shell.execute'),
    'allowed_scopes',jsonb_build_array('content'),
    'allowed_resources',jsonb_build_array('db:dufynd.content_ideas','db:dufynd.zero_budget_queue'),
    'allowed_tools',jsonb_build_array('read_dufynd_zero_budget_content_queue_v1','claim_dufynd_worker_v2','update_dufynd_worker_v2'),
    'verification_policy',jsonb_build_object('kind','content_backlog_prioritize','version',1),
    'supports_retry',true,
    'supports_parallel_execution',false,
    'required_approval_class',null
  ),
  true
)
on conflict(handler_id,handler_version) do update
set contract=excluded.contract,enabled=excluded.enabled;

create or replace function public.plan_dufynd_zero_budget_content_work_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  q jsonb;
  tid text := 'bizplan:zero-budget-content-queue:'||to_char(now() at time zone 'UTC','YYYYMMDD');
  created boolean := false;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-zero-budget-content-planner-v1'));
  q := public.get_dufynd_next_autonomous_action();
  if q->>'state' in ('work_available','work_in_progress','owner_gate') then
    return jsonb_build_object('version',1,'state',q->>'state','created',false,'paid_calls',0,'new_spend_usd',0);
  end if;

  if not exists(
    select 1 from public.dufynd_autonomy_tasks
    where task_id=tid and status='done'
  ) then
    insert into public.dufynd_autonomy_tasks(
      task_id,domain,title,instruction,status,priority,budget_class,
      resource_scope,durability_policy,durable_payload,required_capabilities,forbidden_actions
    ) values(
      tid,'content','Prioritize zero-budget content queue',
      'Rank the existing DUFYND idea backlog against the current zero-budget policy and hard creative gates. Produce NOW/HOLD/HARD-PAUSE evidence only. Never generate or publish media.',
      'ready',94,'free',
      '["db:dufynd.content_ideas","db:dufynd.zero_budget_queue"]'::jsonb,
      'durable',
      '{"kind":"content_backlog_prioritize","version":1}'::jsonb,
      '["content.read","supabase.task_state","supabase.execution_state"]'::jsonb,
      '["gmail.send","social.publish","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
    ) on conflict(task_id) do nothing;
    created := found;
  end if;

  return jsonb_build_object(
    'version',1,'state',case when created then 'work_planned' else 'no_content_queue_work_due' end,
    'created',created,'task_id',case when created then tid else null end,
    'paid_calls',0,'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.plan_dufynd_zero_budget_content_work_v1() from public, anon, authenticated;
grant execute on function public.plan_dufynd_zero_budget_content_work_v1() to service_role, postgres;

create or replace function public.run_dufynd_content_backlog_worker_v1()
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
  perform pg_advisory_xact_lock(hashtext('dufynd-content-backlog-worker-v1'));

  select q.* into t
  from public.dufynd_autonomy_tasks q
  where q.status='ready'
    and q.domain='content'
    and q.budget_class='free'
    and not q.provider_cost_unknown
    and not q.requires_human_approval
    and not q.external_review_required
    and not q.needs_freshness_recheck
    and q.durable_payload->>'kind'='content_backlog_prioritize'
    and q.resource_scope='["db:dufynd.content_ideas","db:dufynd.zero_budget_queue"]'::jsonb
    and public.dufynd_capability_list_valid(q.required_capabilities)
    and public.dufynd_capability_list_valid(q.forbidden_actions)
  order by q.priority desc,q.created_at,q.task_id
  limit 1
  for update;

  if t.task_id is null then
    return jsonb_build_object('version',1,'status','idle','reason','no_content_backlog_task','new_spend_usd',0);
  end if;

  claimed := public.claim_dufynd_worker_v2(t.task_id,'content_backlog_worker_v1',token);
  if claimed is null then
    return jsonb_build_object('version',1,'status','not_claimed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  ok := public.update_dufynd_worker_v2(t.task_id,token,'working','Prioritizing zero-budget content backlog.',null);
  if not ok then
    return jsonb_build_object('version',1,'status','claim_update_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  audit := public.read_dufynd_zero_budget_content_queue_v1();
  evidence := 'Zero-budget content queue: '||audit::text;

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.zero_budget_content_queue_v1','content',audit,94,now())
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

revoke execute on function public.run_dufynd_content_backlog_worker_v1() from public, anon, authenticated;
grant execute on function public.run_dufynd_content_backlog_worker_v1() to service_role, postgres;

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
  business_plan jsonb;
  report jsonb;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-free-planner-v1'));
  before_state := public.get_dufynd_next_autonomous_action();

  if before_state->>'state' in ('work_available','work_in_progress','owner_gate') then
    report := jsonb_build_object(
      'version',4,'observed_at',now(),'state',before_state->>'state',
      'action','none','reason','existing_work_or_gate_already_explains_next_step',
      'queue',before_state,'paid_calls',0,'new_spend_usd',0
    );
  else
    wake_result := public.wake_dufynd_purchase_freshness();
    after_state := public.get_dufynd_next_autonomous_action();

    if after_state->>'state'='work_available' then
      report := jsonb_build_object(
        'version',4,'observed_at',now(),'state','work_replenished',
        'action','purchase_freshness_wake','wake_result',wake_result,
        'queue',after_state,'paid_calls',0,'new_spend_usd',0
      );
    else
      affiliate_plan := public.plan_dufynd_affiliate_work_v1();
      after_state := public.get_dufynd_next_autonomous_action();

      if after_state->>'state'='work_available' then
        report := jsonb_build_object(
          'version',4,'observed_at',now(),'state','work_replenished',
          'action','affiliate_evidence_planning','affiliate_plan',affiliate_plan,
          'queue',after_state,'paid_calls',0,'new_spend_usd',0
        );
      else
        content_plan := public.plan_dufynd_zero_budget_content_work_v1();
        after_state := public.get_dufynd_next_autonomous_action();

        if after_state->>'state'='work_available' then
          report := jsonb_build_object(
            'version',4,'observed_at',now(),'state','work_replenished',
            'action','zero_budget_content_planning','affiliate_plan',affiliate_plan,
            'content_plan',content_plan,'queue',after_state,'paid_calls',0,'new_spend_usd',0
          );
        else
          business_plan := public.plan_dufynd_autonomous_business_work_v1();
          after_state := public.get_dufynd_next_autonomous_action();
          report := jsonb_build_object(
            'version',4,'observed_at',now(),
            'state',case when after_state->>'state'='work_available' then 'work_replenished' else coalesce(business_plan->>'state','planner_gap') end,
            'action','autonomous_business_planning','wake_result',wake_result,
            'affiliate_plan',affiliate_plan,'content_plan',content_plan,'business_plan',business_plan,'queue',after_state,
            'business_next_move',business_plan->>'business_next_move',
            'master_action_required',false,'waiting_external_is_global_blocker',false,
            'paid_calls',0,'new_spend_usd',0
          );
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
  where jobname='dufynd-content-backlog-worker-v1'
  order by jobid desc limit 1;
  if existing_job is not null then perform cron.unschedule(existing_job); end if;
  perform cron.schedule(
    'dufynd-content-backlog-worker-v1',
    '*/2 * * * *',
    'select public.run_dufynd_content_backlog_worker_v1();'
  );
end
$$;

select public.plan_dufynd_free_work_v1();
select public.run_dufynd_content_backlog_worker_v1();
