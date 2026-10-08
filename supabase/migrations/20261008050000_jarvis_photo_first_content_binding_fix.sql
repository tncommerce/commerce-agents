-- Jarvis V5.3: bind content packets to their claimed idea and honor owner-approved photo-first concepts.
-- Deterministic, zero-spend planning only. No media generation, publishing, outreach, or paid calls.

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
      when i.format_id='lifestyle_product_placement'
        and coalesce(i.source,'') like 'owner_%'
        then 'now'
      when i.format_id in (
        'static_text_hook',
        'static_educational_carousel',
        'static_recommendation',
        'static_premium_editorial',
        'static_scent_mood'
      )
        or i.id='idea_ref29_screenproof_001'
        then 'now'
      else 'watch'
    end as lane,
    i.priority
      + case
          when i.format_id='lifestyle_product_placement'
            and coalesce(i.source,'') like 'owner_%' then 35
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
  'version',2,
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

create or replace function public.read_dufynd_content_production_packet_for_idea_v1(
  p_idea_id text
)
returns jsonb
language sql
stable
set search_path to 'public'
as $function$
with idea as (
  select i.*
  from public.dufynd_content_ideas i
  where i.id=p_idea_id
    and i.status='planned'
  limit 1
)
select jsonb_build_object(
  'version',2,
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
    when i.format_id='lifestyle_product_placement' then jsonb_build_array(
      'photo_first_single_scene',
      'story_readable_from_body_language_before_copy',
      'phone_or_product_reveal_must_be_mobile_legible',
      'minimal_copy_only_if_needed',
      'avoid_fake_social_ui',
      'fresh_9_5_visual_qa_required'
    )
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
    'body_rule',case
      when i.format_id='lifestyle_product_placement'
        then 'Let the image carry the joke; use at most one short setup line and one short payoff if the visual alone is not sufficient.'
      else 'Support the premise with one concrete, truthful point; do not over-explain.'
    end,
    'cta_rule',case
      when coalesce(i.objective,'') like '%engagement%' then 'Use one simple opinion question that invites disagreement or examples.'
      when coalesce(i.objective,'') like '%share%' then 'Prefer a tag/send-worthy punchline over explanatory copy.'
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
    'reject_if_product_identity_drifts',true,
    'reject_if_story_requires_long_reading',true
  ),
  'risk_notes',coalesce(i.risk_notes,'[]'::jsonb),
  'paid_generation_allowed',false,
  'publishing_allowed',false,
  'next_step','create_or_select_visual_then_run_fresh_creative_qa',
  'new_spend_usd',0
)
from idea i;
$function$;

create or replace function public.read_dufynd_content_production_packet_v1()
returns jsonb
language sql
stable
set search_path to 'public'
as $function$
select public.read_dufynd_content_production_packet_for_idea_v1(
  (
    select value#>>'{next_content_move,idea_id}'
    from public.dufynd_master_status
    where key='jarvis.zero_budget_content_queue_v1'
  )
);
$function$;

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
  task_idea_id text;
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
    return jsonb_build_object('version',2,'status','idle','reason','no_content_packet_task','new_spend_usd',0);
  end if;

  task_idea_id := t.durable_payload->>'idea_id';
  if task_idea_id is null then
    return jsonb_build_object(
      'version',2,'status','blocked','reason','task_missing_idea_id',
      'task_id',t.task_id,'new_spend_usd',0
    );
  end if;

  claimed := public.claim_dufynd_worker_v2(t.task_id,'content_packet_worker_v1',token);
  if claimed is null then
    return jsonb_build_object('version',2,'status','not_claimed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  ok := public.update_dufynd_worker_v2(
    t.task_id,token,'working',
    'Preparing deterministic zero-budget production packet for '||task_idea_id||'.',
    null
  );
  if not ok then
    return jsonb_build_object('version',2,'status','claim_update_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  packet := public.read_dufynd_content_production_packet_for_idea_v1(task_idea_id);
  if packet is null or packet->>'idea_id' is distinct from task_idea_id then
    ok := public.update_dufynd_worker_v2(
      t.task_id,token,'blocked',
      'Task idea is no longer a planned content candidate.',
      null
    );
    return jsonb_build_object(
      'version',2,'status','blocked','reason','task_idea_not_planned',
      'task_id',t.task_id,'idea_id',task_idea_id,'new_spend_usd',0
    );
  end if;

  evidence := 'Zero-budget production packet: '||packet::text;

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.content_production_packet_v1','content',packet,100,now())
  on conflict(key) do update
  set value=excluded.value,priority=excluded.priority,last_verified_at=excluded.last_verified_at;

  ok := public.update_dufynd_worker_v2(t.task_id,token,'verifying',evidence,null);
  if not ok then
    return jsonb_build_object('version',2,'status','verification_transition_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;
  ok := public.update_dufynd_worker_v2(t.task_id,token,'done',evidence,null);
  if not ok then
    return jsonb_build_object('version',2,'status','completion_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  return jsonb_build_object(
    'version',2,'status','completed','task_id',t.task_id,
    'idea_id',task_idea_id,'packet',packet,'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.read_dufynd_content_production_packet_for_idea_v1(text)
  from public, anon, authenticated;
grant execute on function public.read_dufynd_content_production_packet_for_idea_v1(text)
  to service_role, postgres;

revoke execute on function public.read_dufynd_content_production_packet_v1()
  from public, anon, authenticated;
grant execute on function public.read_dufynd_content_production_packet_v1()
  to service_role, postgres;

revoke execute on function public.run_dufynd_content_packet_worker_v1()
  from public, anon, authenticated;
grant execute on function public.run_dufynd_content_packet_worker_v1()
  to service_role, postgres;

update public.dufynd_handler_contracts
set contract=jsonb_set(
  contract,
  '{allowed_tools}',
  '["read_dufynd_content_production_packet_v1","read_dufynd_content_production_packet_for_idea_v1","claim_dufynd_worker_v2","update_dufynd_worker_v2"]'::jsonb,
  true
)
where handler_id='content_production_packet'
  and handler_version='1';

insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
values(
  'jarvis.zero_budget_content_queue_v1',
  'content',
  public.read_dufynd_zero_budget_content_queue_v1(),
  100,
  now()
)
on conflict(key) do update
set value=excluded.value,
    priority=excluded.priority,
    last_verified_at=excluded.last_verified_at;
