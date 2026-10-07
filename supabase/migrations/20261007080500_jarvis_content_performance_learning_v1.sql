-- Jarvis V5.2: deterministic content-performance learning loop.
-- Consumes internal content_performance_added events, summarizes latest measured
-- social performance, and persists directional learning without auto-publishing
-- or overfitting idea priorities.

create or replace function public.read_dufynd_content_performance_learning_v1()
returns jsonb
language sql
stable
set search_path to 'public'
as $function$
with latest as (
  select distinct on (platform, platform_content_id)
    id, platform, platform_content_id, measured_at, posted_at, views, impressions,
    avg_watch_time_seconds, completion_rate, likes, comments, shares, saves,
    profile_visits, site_clicks, affiliate_clicks, conversions, revenue_eur, metadata
  from public.dufynd_content_performance
  where measured_at >= now()-interval '30 days'
    and platform_content_id is not null
  order by platform, platform_content_id, measured_at desc, id desc
),
tt as (
  select *,
         upper(coalesce(metadata->>'post_type','UNKNOWN')) as post_type,
         coalesce(metadata->>'content_pattern','unknown') as content_pattern
  from latest
  where platform='tiktok'
),
agg as (
  select
    count(*) filter (where post_type='PHOTO')::integer as photo_n,
    count(*) filter (where post_type='VIDEO')::integer as video_n,
    percentile_cont(0.5) within group(order by views)
      filter (where post_type='PHOTO' and views is not null) as photo_median_views,
    percentile_cont(0.5) within group(order by views)
      filter (where post_type='VIDEO' and views is not null) as video_median_views,
    max(views) filter (where post_type='PHOTO') as photo_max_views,
    max(views) filter (where post_type='VIDEO') as video_max_views
  from tt
),
top_rows as (
  select platform_content_id, post_type, content_pattern, views, likes, comments, shares,
         metadata->>'caption' as caption
  from tt
  where views is not null
  order by views desc nulls last, platform_content_id
  limit 5
),
top_video as (
  select platform_content_id, content_pattern, views, likes, metadata->>'caption' as caption
  from tt
  where post_type='VIDEO' and views is not null
  order by views desc nulls last, platform_content_id
  limit 1
)
select jsonb_build_object(
  'version',1,
  'observed_at',now(),
  'window_days',30,
  'source','dufynd_content_performance_latest_per_post',
  'sample_size',(select count(*) from latest),
  'tiktok_sample_size',(select count(*) from tt),
  'confidence',case
    when (select count(*) from tt)>=20 then 'moderate'
    when (select count(*) from tt)>=6 then 'directional_small_sample'
    else 'insufficient_sample'
  end,
  'tiktok',jsonb_build_object(
    'photo_n',coalesce((select photo_n from agg),0),
    'video_n',coalesce((select video_n from agg),0),
    'photo_median_views',(select photo_median_views from agg),
    'video_median_views',(select video_median_views from agg),
    'photo_max_views',(select photo_max_views from agg),
    'video_max_views',(select video_max_views from agg),
    'photo_to_video_median_ratio',case
      when coalesce((select video_median_views from agg),0)>0
        then round(((select photo_median_views from agg)/(select video_median_views from agg))::numeric,2)
      else null
    end,
    'decision',case
      when coalesce((select photo_n from agg),0)>=3
       and coalesce((select video_n from agg),0)>=2
       and coalesce((select photo_median_views from agg),0) >
           coalesce((select video_median_views from agg),0)*1.20
        then 'prioritize_photo_carousel_for_reach'
      else 'mixed_or_insufficient_format_signal'
    end,
    'interpretation','Use this as directional DUFYND account evidence, not a universal platform rule. Keep selective video tests when the creative concept is strong.'
  ),
  'top_posts',coalesce((
    select jsonb_agg(jsonb_build_object(
      'platform_content_id',platform_content_id,
      'post_type',post_type,
      'content_pattern',content_pattern,
      'views',views,
      'likes',likes,
      'comments',comments,
      'shares',shares,
      'caption',caption
    ) order by views desc nulls last, platform_content_id)
    from top_rows
  ),'[]'::jsonb),
  'best_video',coalesce((
    select jsonb_build_object(
      'platform_content_id',platform_content_id,
      'content_pattern',content_pattern,
      'views',views,
      'likes',likes,
      'caption',caption
    ) from top_video
  ),'{}'::jsonb),
  'recommended_next_experiment',case
    when coalesce((select photo_n from agg),0)>=3
     and coalesce((select video_n from agg),0)>=2
     and coalesce((select photo_median_views from agg),0) >
         coalesce((select video_median_views from agg),0)*1.20
      then 'Use photo/carousel as the primary zero-budget reach format; keep video only for concepts with strong proven scroll-stop or existing premium assets.'
    else 'Continue mixed format testing while accumulating more account-specific evidence.'
  end,
  'automatic_priority_mutation',false,
  'new_spend_usd',0
);
$function$;

revoke execute on function public.read_dufynd_content_performance_learning_v1() from public, anon, authenticated;
grant execute on function public.read_dufynd_content_performance_learning_v1() to service_role, postgres;

insert into public.dufynd_handler_contracts(handler_id,handler_version,contract,enabled)
values(
  'content_performance_learning','1',
  jsonb_build_object(
    'handler_id','content_performance_learning',
    'handler_version','1',
    'certification_status','certified',
    'risk_class','low',
    'cost_class','free',
    'durability_class','durable',
    'capabilities',jsonb_build_array('content.read','supabase.task_state','supabase.execution_state'),
    'required_capabilities',jsonb_build_array('content.read','supabase.task_state','supabase.execution_state'),
    'forbidden_actions',jsonb_build_array('gmail.send','social.publish','budget.spend','main.merge','commerce.activate','shell.execute'),
    'allowed_scopes',jsonb_build_array('content'),
    'allowed_resources',jsonb_build_array('db:dufynd.content_performance','db:dufynd.jarvis_inbox','db:dufynd.content_learning'),
    'allowed_tools',jsonb_build_array('read_dufynd_content_performance_learning_v1','claim_dufynd_worker_v2','update_dufynd_worker_v2'),
    'verification_policy',jsonb_build_object('kind','content_performance_learning','version',1),
    'supports_retry',true,
    'supports_parallel_execution',false,
    'required_approval_class',null
  ),
  true
)
on conflict(handler_id,handler_version) do update
set contract=excluded.contract,enabled=excluded.enabled;

create or replace function public.plan_dufynd_content_performance_learning_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  pending_count integer;
  tid text := 'bizplan:content-performance-learning:'||to_char(now() at time zone 'UTC','YYYYMMDDHH24');
  created boolean := false;
begin
  select count(*)::integer into pending_count
  from public.dufynd_jarvis_inbox
  where event_type='content_performance_added'
    and source_type='content_performance'
    and status='pending'
    and fingerprint is null;

  if pending_count=0 then
    return jsonb_build_object(
      'version',1,'state','no_new_performance_events','created',false,
      'pending_events',0,'new_spend_usd',0
    );
  end if;

  if not exists(
    select 1 from public.dufynd_autonomy_tasks
    where task_id=tid and status in ('ready','running','done')
  ) then
    insert into public.dufynd_autonomy_tasks(
      task_id,domain,title,instruction,status,priority,budget_class,
      resource_scope,durability_policy,durable_payload,required_capabilities,forbidden_actions
    ) values(
      tid,'content','Learn from current social performance',
      'Aggregate the latest measured DUFYND social performance into directional format/pattern evidence. Do not publish, generate media, spend, or mutate content priorities automatically.',
      'ready',91,'free',
      '["db:dufynd.content_performance","db:dufynd.jarvis_inbox","db:dufynd.content_learning"]'::jsonb,
      'durable',
      '{"kind":"content_performance_learning","version":1}'::jsonb,
      '["content.read","supabase.task_state","supabase.execution_state"]'::jsonb,
      '["gmail.send","social.publish","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
    ) on conflict(task_id) do nothing;
    created := found;
  end if;

  return jsonb_build_object(
    'version',1,
    'state',case when created then 'work_planned' else 'learning_task_already_exists' end,
    'created',created,'task_id',tid,'pending_events',pending_count,'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.plan_dufynd_content_performance_learning_v1() from public, anon, authenticated;
grant execute on function public.plan_dufynd_content_performance_learning_v1() to service_role, postgres;

create or replace function public.run_dufynd_content_performance_worker_v1()
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
  processed_events integer := 0;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-content-performance-worker-v1'));

  select q.* into t
  from public.dufynd_autonomy_tasks q
  where q.status='ready'
    and q.domain='content'
    and q.budget_class='free'
    and not q.provider_cost_unknown
    and not q.requires_human_approval
    and not q.external_review_required
    and not q.needs_freshness_recheck
    and q.durable_payload->>'kind'='content_performance_learning'
    and q.resource_scope='["db:dufynd.content_performance","db:dufynd.jarvis_inbox","db:dufynd.content_learning"]'::jsonb
    and public.dufynd_capability_list_valid(q.required_capabilities)
    and public.dufynd_capability_list_valid(q.forbidden_actions)
  order by q.priority desc,q.created_at,q.task_id
  limit 1
  for update;

  if t.task_id is null then
    return jsonb_build_object('version',1,'status','idle','reason','no_content_performance_task','new_spend_usd',0);
  end if;

  claimed := public.claim_dufynd_worker_v2(t.task_id,'content_performance_worker_v1',token);
  if claimed is null then
    return jsonb_build_object('version',1,'status','not_claimed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  ok := public.update_dufynd_worker_v2(
    t.task_id,token,'working','Aggregating latest DUFYND social performance evidence.',null
  );
  if not ok then
    return jsonb_build_object('version',1,'status','claim_update_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  audit := public.read_dufynd_content_performance_learning_v1();
  evidence := 'Content performance learning: '||audit::text;

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.content_performance_learning_v1','content',audit,91,now())
  on conflict(key) do update
  set value=excluded.value,priority=excluded.priority,last_verified_at=excluded.last_verified_at;

  with claimed_events as (
    select inbox_id
    from public.dufynd_jarvis_inbox
    where event_type='content_performance_added'
      and source_type='content_performance'
      and status='pending'
      and fingerprint is null
    order by inbox_id
    limit 200
    for update skip locked
  ), updated as (
    update public.dufynd_jarvis_inbox j
    set status='done',
        processed_at=now(),
        attempts=j.attempts+1,
        last_error=null,
        updated_at=now(),
        processing_status='content_performance_learning_v1'
    from claimed_events c
    where j.inbox_id=c.inbox_id
    returning j.inbox_id
  )
  select count(*)::integer into processed_events from updated;

  ok := public.update_dufynd_worker_v2(t.task_id,token,'verifying',evidence,null);
  if not ok then
    return jsonb_build_object('version',1,'status','verification_transition_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  ok := public.update_dufynd_worker_v2(t.task_id,token,'done',evidence,null);
  if not ok then
    return jsonb_build_object('version',1,'status','completion_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  return jsonb_build_object(
    'version',1,'status','completed','task_id',t.task_id,
    'processed_events',processed_events,'audit',audit,'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.run_dufynd_content_performance_worker_v1() from public, anon, authenticated;
grant execute on function public.run_dufynd_content_performance_worker_v1() to service_role, postgres;

create or replace function public.run_dufynd_content_performance_cycle_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  planned jsonb;
  worked jsonb;
begin
  planned := public.plan_dufynd_content_performance_learning_v1();
  worked := public.run_dufynd_content_performance_worker_v1();
  return jsonb_build_object(
    'version',1,'planned',planned,'worker',worked,'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.run_dufynd_content_performance_cycle_v1() from public, anon, authenticated;
grant execute on function public.run_dufynd_content_performance_cycle_v1() to service_role, postgres;

do $$
declare existing_job bigint;
begin
  select jobid into existing_job from cron.job
  where jobname='dufynd-content-performance-learning-v1'
  order by jobid desc limit 1;
  if existing_job is not null then perform cron.unschedule(existing_job); end if;
  perform cron.schedule(
    'dufynd-content-performance-learning-v1',
    '*/10 * * * *',
    'select public.run_dufynd_content_performance_cycle_v1();'
  );
end
$$;
