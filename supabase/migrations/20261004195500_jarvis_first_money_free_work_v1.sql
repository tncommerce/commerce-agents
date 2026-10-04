-- JARVIS First-Money Free Work V1
-- Event-driven, deterministic, free-only. No publishing, outreach, activation, credentials or paid calls.

create or replace function public.read_dufynd_first_money_runtime() returns jsonb
language sql stable security invoker set search_path=public as $$
with cfg as (
  select value
  from public.dufynd_master_status
  where key='continuity.checkpoint.ceo_radar'
),
ids as (
  select
    value->'first_money_schedule'->>'content_id' as content_id,
    value->'first_money_schedule'->>'experiment_id' as experiment_id,
    public.dufynd_parse_timestamp(value->'first_money_schedule'->>'instagram') as instagram_at,
    public.dufynd_parse_timestamp(value->'first_money_schedule'->>'tiktok') as tiktok_at
  from cfg
),
f as (
  select
    coalesce(sum(page_views),0)::bigint as page_views,
    coalesce(sum(landing_sessions),0)::bigint as landing_sessions,
    coalesce(sum(product_views),0)::bigint as product_views,
    coalesce(sum(merchant_clickouts),0)::bigint as merchant_clickouts,
    min(first_seen_at) as first_seen_at,
    max(last_seen_at) as last_seen_at,
    coalesce(jsonb_agg(
      jsonb_build_object(
        'source',acquisition_source,
        'campaign_id',campaign_id,
        'landing_sessions',landing_sessions,
        'product_views',product_views,
        'merchant_clickouts',merchant_clickouts,
        'last_seen_at',last_seen_at
      )
      order by acquisition_source
    ) filter (where content_id is not null),'[]'::jsonb) as by_source
  from public.dufynd_content_funnel_v1
  where content_id=(select content_id from ids)
),
p as (
  select
    offer_id, product_id, enabled, last_verified_at,
    last_verified_at + make_interval(hours=>max_age_hours-safety_window_hours) as next_refresh_due_at,
    last_verified_at + make_interval(hours=>max_age_hours) as expires_at,
    last_result
  from public.dufynd_purchase_verification_targets
  where product_id='SC-RABANNE-1-MILLION-EDT-100'
  order by last_verified_at desc
  limit 1
)
select jsonb_build_object(
  'version',1,
  'observed_at',now(),
  'content_id',(select content_id from ids),
  'experiment_id',(select experiment_id from ids),
  'schedule',jsonb_build_object(
    'instagram',(select instagram_at from ids),
    'tiktok',(select tiktok_at from ids)
  ),
  'phase',case
    when (select instagram_at from ids) is null then 'schedule_unknown'
    when now() < least((select instagram_at from ids),(select tiktok_at from ids)) then 'prelaunch'
    when now() <= greatest((select instagram_at from ids),(select tiktok_at from ids)) + interval '24 hours' then 'live_measurement_window'
    else 'post_measurement_window'
  end,
  'funnel',jsonb_build_object(
    'page_views',(select page_views from f),
    'landing_sessions',(select landing_sessions from f),
    'product_views',(select product_views from f),
    'merchant_clickouts',(select merchant_clickouts from f),
    'first_seen_at',(select first_seen_at from f),
    'last_seen_at',(select last_seen_at from f),
    'by_source',(select by_source from f)
  ),
  'next_evidence',case
    when (select instagram_at from ids) is null then 'schedule_evidence'
    when now() < least((select instagram_at from ids),(select tiktok_at from ids)) then 'publication_evidence'
    when (select landing_sessions from f)=0 then 'qualified_session'
    when (select product_views from f)=0 then 'product_view'
    when (select merchant_clickouts from f)=0 then 'merchant_clickout'
    else 'affiliate_transaction_evidence'
  end,
  'purchase_evidence',coalesce((
    select jsonb_build_object(
      'offer_id',offer_id,
      'product_id',product_id,
      'enabled',enabled,
      'last_verified_at',last_verified_at,
      'next_refresh_due_at',next_refresh_due_at,
      'expires_at',expires_at,
      'decision',last_result->>'decision',
      'stock',last_result->>'stock',
      'price_eur',last_result->'price_eur'
    ) from p
  ),'{}'::jsonb),
  'sales_truth',jsonb_build_object(
    'transactions','external_network_evidence_required',
    'commission','external_network_evidence_required',
    'clickout_is_sale',false
  )
);
$$;

create or replace function public.read_dufynd_thin_state() returns jsonb
language sql security invoker set search_path=public as $$
select jsonb_build_object(
 'version',2,
 'observed_at',now(),
 'queue_counts',(select coalesce(jsonb_object_agg(status,n),'{}') from (select status,count(*) n from public.dufynd_autonomy_tasks group by status) q),
 'active_leases',(select count(*) from public.dufynd_autonomy_tasks where released_at is null and worker_state in ('claimed','working','verifying')),
 'stale_leases',(select count(*) from public.dufynd_autonomy_tasks where released_at is null and worker_state in ('claimed','working','verifying') and coalesce(lease_expires_at,'-infinity')<=now()),
 'open_reservations',(select count(*) from public.dufynd_budget_reservations where status in ('reserved','dispatched','cost_unknown')),
 'provider_cost_unknown',exists(select 1 from public.dufynd_autonomy_tasks where provider_cost_unknown),
 'pending_owner_gates',(select coalesce(jsonb_agg(jsonb_build_object('decision_id',decision_id,'decision_token',decision_token,'action_type',action_type) order by created_at),'[]') from public.dufynd_human_decisions where status='pending'),
 'ci',(select value from public.dufynd_master_status where key='jarvis.thin_v1.ci'),
 'supervisor_checked_at',(select last_verified_at from public.dufynd_master_status where key='jarvis.supervisor_v2.health'),
 'business_checkpoint',(select jsonb_build_object('verified_at',last_verified_at,'age_seconds',extract(epoch from now()-last_verified_at),'measurement',value->'measurement','first_money_schedule',value->'first_money_schedule','schedule_source','ceo_checkpoint_only','publication_verified',false) from public.dufynd_master_status where key='continuity.checkpoint.ceo_radar'),
 'first_money_runtime',public.read_dufynd_first_money_runtime(),
 'certified_free_handlers',(select coalesce(jsonb_agg(handler_id order by handler_id),'[]') from public.dufynd_handler_contracts where enabled and contract->>'cost_class'='free' and contract->>'certification_status'='certified'),
 'recent_first_money_events',(select coalesce(jsonb_agg(jsonb_build_object('event_id',event_id,'event_type',event_type,'observed_at',observed_at)),'[]') from (select event_id,event_type,observed_at from public.dufynd_jarvis_inbox where observed_at>now()-interval '24 hours' and (payload::text like '%one_million%' or payload::text like '%FIRST-MONEY%' or payload::text like '%fms_1m%') order by observed_at desc limit 20) e),
 'observer_health',public.get_dufynd_observer_health(),
 'paid_calls_this_loop',0,'new_spend_usd',0,'budget_window_used',null,
 'limitations','No publishing, activation, outreach, credentials, arbitrary engineering or paid workers. Funnel auditing and purchase-evidence refresh are deterministic/free; sales/commission still require network evidence.'
);
$$;

insert into public.dufynd_autonomy_tasks(
  task_id,domain,title,instruction,status,priority,budget_class,
  resource_scope,durability_policy,durable_payload,forbidden_actions
)
values(
  'jarvis_first_money_readiness_audit_20261004',
  'supervisor',
  'First-Money launch readiness and funnel evidence audit',
  'Persist bounded First-Money funnel, purchase-evidence and supervisor metadata only.',
  'ready',100,'free',
  '["db:jarvis.supervisor_v2.health"]'::jsonb,
  'durable',
  '{"kind":"supervisor_state_audit","steps":1,"interval_seconds":2}'::jsonb,
  '["gmail.send","social.publish","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
)
on conflict(task_id) do nothing;

create or replace function public.queue_dufynd_first_money_signal_audit() returns trigger
language plpgsql security definer set search_path=public as $$
declare target_content text; bucket timestamptz; tid text;
begin
  select value->'first_money_schedule'->>'content_id' into target_content
  from public.dufynd_master_status
  where key='continuity.checkpoint.ceo_radar';

  if target_content is null
     or new.content_id is distinct from target_content
     or new.event not in ('page_view','fragrance_detail_view','offer_section_view','offer_section_open','merchant_clickout') then
    return new;
  end if;

  bucket:=date_trunc('hour',new.occurred_at)
    + floor(extract(minute from new.occurred_at)/10)::int * interval '10 minutes';
  tid:='first-money-signal:'||to_char(bucket at time zone 'UTC','YYYYMMDDHH24MI');

  insert into public.dufynd_autonomy_tasks(
    task_id,domain,title,instruction,status,priority,budget_class,
    resource_scope,durability_policy,durable_payload,forbidden_actions
  )
  values(
    tid,'supervisor','First-Money live funnel signal audit',
    'Persist the current bounded First-Money funnel and supervisor evidence after a real analytics signal.',
    'ready',100,'free',
    '["db:jarvis.supervisor_v2.health"]'::jsonb,
    'durable',
    '{"kind":"supervisor_state_audit","steps":1,"interval_seconds":2}'::jsonb,
    '["gmail.send","social.publish","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
  )
  on conflict(task_id) do nothing;

  return new;
end $$;

drop trigger if exists dufynd_first_money_signal_audit on public.scentai_analytics_events;
create trigger dufynd_first_money_signal_audit
after insert on public.scentai_analytics_events
for each row execute function public.queue_dufynd_first_money_signal_audit();

revoke all on function public.read_dufynd_first_money_runtime(),public.queue_dufynd_first_money_signal_audit() from public,anon,authenticated;
grant execute on function public.read_dufynd_first_money_runtime(),public.queue_dufynd_first_money_signal_audit() to service_role;
