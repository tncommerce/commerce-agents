-- Historical traffic is unknown unless positively marked QA. Do not call it organic.
alter table public.scentai_analytics_events add column traffic_class text not null default 'unclassified'
 check(traffic_class in ('visitor','internal_qa','unclassified'));
create index scentai_analytics_qa_session on public.scentai_analytics_events(session_key) where traffic_class='internal_qa';
update public.scentai_analytics_events set traffic_class='internal_qa'
 where concat_ws(':',source,acquisition_source,campaign_id,content_id,surface,session_key) ~* '(^|[._:-])(qa|test|smoke|preview)([._:-]|$)';
create view public.dufynd_visitor_analytics with (security_invoker=true) as
 select e.* from public.scentai_analytics_events e where e.traffic_class='visitor'
 and concat_ws(':',e.source,e.acquisition_source,e.campaign_id,e.content_id,e.surface) !~* '(^|[._:-])(qa|test|smoke|preview)([._:-]|$)'
 and not exists(select 1 from public.scentai_analytics_events q where q.session_key=e.session_key and q.traffic_class='internal_qa');
revoke all on public.dufynd_visitor_analytics from public,anon,authenticated;
grant select on public.dufynd_visitor_analytics to service_role;
-- Launch-day evidence only. No publishing, network transactions, costs or product writes.
create or replace function public.read_dufynd_first_money_runtime() returns jsonb
language sql stable security invoker set search_path=public as $$
with ids as (
 select value->>'content_id' content_id,
 value->>'experiment_id' experiment_id,
 public.dufynd_parse_timestamp(value->>'instagram') instagram_at,
 public.dufynd_parse_timestamp(value->>'tiktok') tiktok_at
 from (select public.dufynd_first_money_measurement_target() as value) cfg
), eligible as (
 select e.* from public.dufynd_visitor_analytics e cross join ids i
 where e.content_id=i.content_id and e.campaign_id=i.experiment_id
 and e.acquisition_source in ('instagram','tiktok')
 and e.occurred_at>=case e.acquisition_source when 'instagram' then i.instagram_at else i.tiktok_at end
 and e.occurred_at<=now()
 and coalesce(e.source,'') !~* '(^|[._:-])(qa|test|smoke|preview)([._:-]|$)'
 and coalesce(e.session_key,'') !~* '^(qa|test|smoke|preview)[._:-]'
 and (e.event='page_view' and (e.product_id is null or e.product_id='SC-RABANNE-1-MILLION-EDT-100')
 or e.event in ('fragrance_detail_view','offer_section_view','offer_section_open','merchant_clickout')
 and e.product_id='SC-RABANNE-1-MILLION-EDT-100')
), f as (
 select count(*) filter(where event='page_view') page_views,
 count(distinct session_key) filter(where event='page_view') landing_sessions,
 count(*) filter(where event='fragrance_detail_view') product_views,
 count(*) filter(where event='offer_section_view') offer_views,
 count(*) filter(where event='offer_section_open') offer_opens,
 count(*) filter(where event='merchant_clickout') merchant_clickouts,
 min(occurred_at) first_seen_at,max(occurred_at) last_seen_at from eligible
), p as (
 select * from public.dufynd_purchase_verification_targets
 where product_id='SC-RABANNE-1-MILLION-EDT-100' order by last_verified_at desc limit 1
)
select jsonb_build_object('version',3,'observed_at',now(),
 'content_id',i.content_id,'experiment_id',i.experiment_id,
 'source','scentai_analytics_events','analytics_provenance','launch_attributed_excludes_prelaunch',
 'basis','Exact content/campaign/source/product after each platform launch; prelaunch and unrelated traffic excluded. Attribution does not prove organic reach. Clickout is not a sale.',
 'schedule',jsonb_build_object('instagram',i.instagram_at,'tiktok',i.tiktok_at),
 'phase',case when i.instagram_at is null and i.tiktok_at is null then 'schedule_unknown'
 when now()<least(i.instagram_at,i.tiktok_at) then 'prelaunch'
 when now()<=greatest(i.instagram_at,i.tiktok_at)+interval '24 hours' then 'live_measurement_window'
 else 'post_measurement_window' end,
 'funnel',to_jsonb(f)||jsonb_build_object('by_source',(
 select coalesce(jsonb_agg(to_jsonb(s) order by acquisition_source),'[]') from (
 select acquisition_source,count(distinct session_key) filter(where event='page_view') landing_sessions,
 count(*) filter(where event='fragrance_detail_view') product_views,
 count(*) filter(where event='offer_section_view') offer_views,
 count(*) filter(where event='offer_section_open') offer_opens,
 count(*) filter(where event='merchant_clickout') merchant_clickouts,max(occurred_at) last_seen_at
 from eligible group by acquisition_source) s)),
 'decision_state',case when f.merchant_clickouts>0 then 'purchase_interest_reached'
 when f.offer_views+f.offer_opens>0 then 'purchase_options_viewed'
 when f.product_views>0 then 'product_interest'
 when f.landing_sessions>0 then 'traffic_reached_dufynd' else 'waiting_first_signal' end,
 'next_evidence',case when i.instagram_at is null and i.tiktok_at is null then 'schedule_evidence'
 when now()<least(i.instagram_at,i.tiktok_at) then 'publication_evidence'
 when f.landing_sessions=0 then 'qualified_session' when f.product_views=0 then 'product_view'
 when f.offer_views+f.offer_opens=0 then 'offer_view' when f.merchant_clickouts=0 then 'merchant_clickout'
 else 'affiliate_transaction_evidence' end,
 'publication_verified',false,
 'recent_signals',(select coalesce(jsonb_agg(to_jsonb(z) order by occurred_at desc),'[]') from (
 select event_id,event,occurred_at from eligible order by occurred_at desc,id desc limit 8) z),
 'purchase_evidence',coalesce((select jsonb_build_object('offer_id',offer_id,'product_id',product_id,'enabled',enabled,
 'last_verified_at',last_verified_at,'next_refresh_due_at',last_verified_at+make_interval(hours=>max_age_hours-safety_window_hours),
 'expires_at',last_verified_at+make_interval(hours=>max_age_hours),'decision',last_result->>'decision',
 'stock',last_result->>'stock','price_eur',last_result->'price_eur') from p),'{}'),
 'sales_truth',jsonb_build_object('transactions','external_network_evidence_required','commission','external_network_evidence_required',
 'clickout_is_sale',false,'network_ingestion_connected',false)) from ids i cross join f;
$$;

create or replace function public.queue_dufynd_first_money_signal_audit() returns trigger
language plpgsql security definer set search_path=public as $$
declare cfg jsonb; launch_at timestamptz; bucket timestamptz; tid text;
begin
 if new.traffic_class<>'visitor' or concat_ws(':',new.source,new.acquisition_source,new.campaign_id,new.content_id,new.surface) ~* '(^|[._:-])(qa|test|smoke|preview)([._:-]|$)' then return new; end if;
 cfg:=public.dufynd_first_money_measurement_target();
 launch_at:=public.dufynd_parse_timestamp(cfg->>new.acquisition_source);
 if cfg->>'content_id' is null or cfg->>'experiment_id' is null
 or new.content_id is distinct from cfg->>'content_id' or new.campaign_id is distinct from cfg->>'experiment_id'
 or new.acquisition_source is null or new.acquisition_source not in ('instagram','tiktok')
 or launch_at is null or new.occurred_at<launch_at or new.occurred_at>now()
 or coalesce(new.source,'') ~* '(^|[._:-])(qa|test|smoke|preview)([._:-]|$)'
 or coalesce(new.session_key,'') ~* '^(qa|test|smoke|preview)[._:-]'
 or new.event not in ('page_view','fragrance_detail_view','offer_section_view','offer_section_open','merchant_clickout')
 or (new.event='page_view' and new.product_id is not null and new.product_id<>'SC-RABANNE-1-MILLION-EDT-100')
 or (new.event<>'page_view' and new.product_id is distinct from 'SC-RABANNE-1-MILLION-EDT-100') then return new; end if;
 -- Use ingestion time: delayed or client-provided timestamps cannot create unbounded historical buckets.
 bucket:=date_trunc('hour',now())+floor(extract(minute from now())/10)::int*interval '10 minutes';
 tid:='first-money-signal:'||to_char(bucket at time zone 'UTC','YYYYMMDDHH24MI')||':'||
 substr(encode(sha256(convert_to(jsonb_build_array(cfg->>'content_id',cfg->>'experiment_id')::text,'UTF8')),'hex'),1,16);
 insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,priority,budget_class,
 resource_scope,durability_policy,durable_payload,forbidden_actions)
 values(tid,'supervisor','First-Money live funnel signal audit','Persist bounded launch-attributed funnel evidence only.',
 'ready',100,'free','["db:jarvis.supervisor_v2.health"]','durable',
 '{"kind":"supervisor_state_audit","steps":1,"interval_seconds":2}',
 '["gmail.send","social.publish","budget.spend","main.merge","commerce.activate","shell.execute"]')
 on conflict(task_id) do nothing;
 return new;
end $$;


revoke all on function public.read_dufynd_first_money_runtime(),public.queue_dufynd_first_money_signal_audit() from public,anon,authenticated;
grant execute on function public.read_dufynd_first_money_runtime(),public.queue_dufynd_first_money_signal_audit() to service_role;
-- Jarvis V5.0: First-Money measurement continuity.
-- Adds a deterministic zero-spend measurement worker and distinguishes true
-- planner starvation from a legitimate wait for qualified external traffic.

create or replace function public.read_dufynd_first_money_measurement_audit_v1()
returns jsonb
language plpgsql
stable
set search_path to 'public'
as $function$
declare
  fm jsonb;
  campaign text;
  content text;
  launch_at timestamptz;
  prelaunch_events integer := 0;
  post_landing integer := 0;
  post_product integer := 0;
  post_offer integer := 0;
  post_clickout integer := 0;
  organic_clickouts integer := 0;
  instrumentation_proven boolean := false;
  decision text;
  next_move text;
begin
  fm := public.read_dufynd_first_money_runtime();
  campaign := fm->>'experiment_id';
  content := fm->>'content_id';
  launch_at := nullif(fm#>>'{schedule,instagram}','')::timestamptz;

  if launch_at is not null then
    select count(*)::integer
      into prelaunch_events
    from public.scentai_analytics_events
    where occurred_at < launch_at
      and campaign_id=campaign
      and content_id=content
      and acquisition_source='instagram'
      and event in ('page_view','fragrance_detail_view','offer_section_view','merchant_clickout');

    select count(distinct session_key)::integer
      into post_landing
    from public.dufynd_visitor_analytics
    where occurred_at >= launch_at
      and campaign_id=campaign
      and content_id=content
      and acquisition_source='instagram'
      and event='page_view'
      and surface='acquisition_landing';

    select count(*)::integer
      into post_product
    from public.dufynd_visitor_analytics
    where occurred_at >= launch_at
      and campaign_id=campaign
      and content_id=content
      and acquisition_source='instagram'
      and event='fragrance_detail_view';

    select count(*)::integer
      into post_offer
    from public.dufynd_visitor_analytics
    where occurred_at >= launch_at
      and campaign_id=campaign
      and content_id=content
      and acquisition_source='instagram'
      and event='offer_section_view';

    select count(*)::integer
      into post_clickout
    from public.dufynd_visitor_analytics
    where occurred_at >= launch_at
      and campaign_id=campaign
      and content_id=content
      and acquisition_source='instagram'
      and event='merchant_clickout';

    select count(*)::integer
      into organic_clickouts
    from public.dufynd_visitor_analytics
    where occurred_at >= launch_at
      and event='merchant_clickout'
      and campaign_id is null
      and content_id is null;
  end if;

  instrumentation_proven := prelaunch_events > 0;

  if launch_at is null then
    decision := 'publication_schedule_missing';
    next_move := 'verify_publication_schedule_truth';
  elsif post_clickout > 0 then
    decision := 'attributed_clickout_signal_present';
    next_move := 'verify_network_transaction_evidence_without_treating_clickout_as_sale';
  elsif post_landing > 0 then
    decision := 'qualified_traffic_present_no_clickout';
    next_move := 'optimize_offer_transition_and_clickout_conversion';
  elsif instrumentation_proven then
    decision := 'waiting_for_qualified_distribution_signal';
    next_move := 'produce_and_publish_owner_approved_reach_content_then_measure_again';
  else
    decision := 'measurement_instrumentation_unproven';
    next_move := 'repair_or_verify_campaign_attribution_instrumentation';
  end if;

  return jsonb_build_object(
    'version',2,
    'traffic_provenance','visitor_class_excludes_qa_sessions_and_unclassified_history',
    'internal_qa_events',(select count(*) from public.scentai_analytics_events where traffic_class='internal_qa'),
    'unclassified_events',(select count(*) from public.scentai_analytics_events where traffic_class='unclassified'),
    'observed_at',now(),
    'experiment_id',campaign,
    'content_id',content,
    'launch_at',launch_at,
    'prelaunch_attributed_events',prelaunch_events,
    'instrumentation_proven',instrumentation_proven,
    'postlaunch_landing_sessions',post_landing,
    'postlaunch_product_views',post_product,
    'postlaunch_offer_views',post_offer,
    'postlaunch_merchant_clickouts',post_clickout,
    'unattributed_visitor_clickouts_since_launch',organic_clickouts,
    'clickout_is_sale',false,
    'network_ingestion_connected',coalesce((fm#>>'{sales_truth,network_ingestion_connected}')::boolean,false),
    'decision',decision,
    'next_move',next_move,
    'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.read_dufynd_first_money_measurement_audit_v1() from public, anon, authenticated;
grant execute on function public.read_dufynd_first_money_measurement_audit_v1() to service_role, postgres;

