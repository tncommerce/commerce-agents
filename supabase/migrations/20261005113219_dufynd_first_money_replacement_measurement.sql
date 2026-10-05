-- Read-only target selection. No post, approval, merchant or publication mutation.
create function public.dufynd_first_money_measurement_target() returns jsonb
language plpgsql stable security invoker set search_path=public as $$
declare replacement jsonb; original jsonb;
begin
 select value into replacement from public.dufynd_master_status where key='first_money.social_quality_incident.20261005';
 if replacement->>'status' in ('replacement_scheduled','replacement_published','replacement_publication_verified')
 and replacement->>'publishing_authorized'='true'
 and replacement->>'instagram_auto_publish'='true' and replacement->>'instagram_draft'='false'
 and coalesce(replacement->>'owner_publish_approval_source','')<>''
 and coalesce(replacement->>'replacement_content_id','') ~ '^[A-Za-z0-9._:-]{1,80}$'
 and coalesce(replacement->>'replacement_experiment_id','') ~ '^[A-Za-z0-9._:-]{1,80}$'
 and public.dufynd_parse_timestamp(replacement->>'instagram_scheduled_at') is not null then
  return jsonb_build_object('content_id',replacement->>'replacement_content_id',
   'experiment_id',replacement->>'replacement_experiment_id','instagram',replacement->>'instagram_scheduled_at',
   'tiktok',null,'target_source','approved_replacement_schedule');
 end if;
 -- Removed/stopped content is history, not a fallback active launch.
 if replacement->>'instagram_state'='owner_confirmed_removed' or replacement->>'tiktok_state'='stopped_before_publish' then return '{}'; end if;
 select value->'first_money_schedule' into original from public.dufynd_master_status where key='continuity.checkpoint.ceo_radar';
 return coalesce(original,'{}');
end $$;
revoke all on function public.dufynd_first_money_measurement_target() from public,anon,authenticated;
grant execute on function public.dufynd_first_money_measurement_target() to service_role;

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
 select e.* from public.scentai_analytics_events e cross join ids i
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
