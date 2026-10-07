-- Jarvis V5.1: repair performance->Jarvis learning trigger schema drift.
-- The performance table does not own content_idea_id; derive it through the
-- referenced content asset or optional metadata instead of dereferencing a
-- nonexistent NEW field.

create or replace function public.queue_dufynd_performance_for_jarvis()
returns trigger
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  resolved_content_idea_id text;
begin
  select a.content_idea_id
    into resolved_content_idea_id
  from public.dufynd_content_assets a
  where a.id = new.content_asset_id
  limit 1;

  resolved_content_idea_id := coalesce(
    resolved_content_idea_id,
    nullif(new.metadata->>'content_idea_id','')
  );

  perform public.enqueue_dufynd_jarvis_event(
    'content_performance_added',
    'content_performance',
    new.id::text,
    jsonb_build_object(
      'performance_id', new.id,
      'content_asset_id', new.content_asset_id,
      'content_idea_id', resolved_content_idea_id,
      'platform', new.platform,
      'platform_content_id', new.platform_content_id,
      'posted_at', new.posted_at,
      'views', new.views,
      'impressions', new.impressions,
      'avg_watch_time_seconds', new.avg_watch_time_seconds,
      'completion_rate', new.completion_rate,
      'likes', new.likes,
      'comments', new.comments,
      'shares', new.shares,
      'saves', new.saves,
      'profile_visits', new.profile_visits,
      'site_clicks', new.site_clicks,
      'affiliate_clicks', new.affiliate_clicks,
      'conversions', new.conversions,
      'revenue_eur', new.revenue_eur,
      'metadata', new.metadata
    )
  );

  return new;
end;
$function$;

revoke execute on function public.queue_dufynd_performance_for_jarvis() from public, anon, authenticated;
grant execute on function public.queue_dufynd_performance_for_jarvis() to service_role, postgres;

-- Runtime schema assertion so this exact mismatch cannot silently regress.
do $$
begin
  if exists(
    select 1
    from information_schema.columns
    where table_schema='public'
      and table_name='dufynd_content_performance'
      and column_name='content_idea_id'
  ) then
    raise notice 'dufynd_content_performance now has content_idea_id; trigger remains compatible';
  end if;

  if not exists(
    select 1
    from information_schema.columns
    where table_schema='public'
      and table_name='dufynd_content_assets'
      and column_name='content_idea_id'
  ) then
    raise exception 'content asset linkage missing: dufynd_content_assets.content_idea_id';
  end if;
end
$$;
