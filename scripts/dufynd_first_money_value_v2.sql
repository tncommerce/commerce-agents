-- READ ONLY. Bind $1/$2 to an explicit <=7-day UTC interval.
-- No session identifiers, raw events, visitors or network sales are fabricated.
with events as (
 select * from public.scentai_analytics_events
 where occurred_at > $1::timestamptz and occurred_at <= $2::timestamptz
), sessions as (
 select e.session_key,
 case
  when exists(select 1 from public.scentai_analytics_events h
   where h.session_key=e.session_key and h.traffic_class in ('qa','internal_qa','owner')) then 'qa'
  when exists(select 1 from public.scentai_analytics_events h
   where h.session_key=e.session_key and h.traffic_class='bot') then 'bot'
  when bool_and(coalesce(e.traffic_class,'unknown')='visitor') then 'visitor_unverified'
  else 'unknown' end as class,
 bool_or(coalesce(e.acquisition_source,e.source,'unknown') in ('instagram','tiktok','youtube')
  and coalesce(e.campaign_id,'')<>'') as tagged_social
 from events e group by e.session_key
), eligible as (
 select e.* from events e join sessions s on e.session_key is not distinct from s.session_key
 where s.class not in ('qa','bot')
)
select jsonb_build_object(
 'query_version',1,
 'complete',not exists(select 1 from events where event_id is null or session_key is null),
 'window_start',$1::timestamptz,'window_end',$2::timestamptz,
 'events',(select count(*) from events),
 'unique_events',(select count(distinct event_id) from events),
 'sessions',(select count(*) from sessions),
 'qa_sessions',(select count(*) from sessions where class='qa'),
 'bot_sessions',(select count(*) from sessions where class='bot'),
 'unknown_sessions',(select count(*) from sessions where class='unknown'),
 'visitor_unverified_sessions',(select count(*) from sessions where class='visitor_unverified'),
 'social_tagged_sessions',(select count(*) from sessions where tagged_social and class not in ('qa','bot')),
 'product_views',(select count(*) from eligible where event='fragrance_detail_view'),
 'offer_views',(select count(*) from eligible where event='offer_section_view'),
 'merchant_clickouts',(select count(*) from eligible where event='merchant_clickout'),
 'network_report_available',false
) as evidence;
