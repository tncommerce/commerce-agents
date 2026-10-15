-- CONSENT-26 / PRIVACY retention: bounded first-party analytics lifecycle.
-- This migration is intentionally safe to load in CI Postgres without pg_cron.
-- In Supabase, an existing pg_cron installation receives one idempotently named job.

create or replace function public.purge_dufynd_analytics_retention(
  p_now timestamptz default now()
)
returns jsonb
language plpgsql
security invoker
set search_path=public
as $$
declare
  deleted_visitors bigint := 0;
  deleted_internal_qa bigint := 0;
  deleted_unclassified bigint := 0;
begin
  if p_now is null then
    raise exception 'retention reference time is required';
  end if;

  delete from public.scentai_analytics_events
  where traffic_class = 'visitor'
    and occurred_at < p_now - interval '90 days';
  get diagnostics deleted_visitors = row_count;

  delete from public.scentai_analytics_events
  where traffic_class = 'internal_qa'
    and occurred_at < p_now - interval '30 days';
  get diagnostics deleted_internal_qa = row_count;

  delete from public.scentai_analytics_events
  where traffic_class = 'unclassified'
    and occurred_at < p_now - interval '30 days';
  get diagnostics deleted_unclassified = row_count;

  return jsonb_build_object(
    'version', 1,
    'evaluated_at', p_now,
    'visitor_retention_days', 90,
    'diagnostic_retention_days', 30,
    'deleted_visitor', deleted_visitors,
    'deleted_internal_qa', deleted_internal_qa,
    'deleted_unclassified', deleted_unclassified,
    'deleted_total', deleted_visitors + deleted_internal_qa + deleted_unclassified
  );
end;
$$;

revoke all on function public.purge_dufynd_analytics_retention(timestamptz)
  from public, anon, authenticated;
grant execute on function public.purge_dufynd_analytics_retention(timestamptz)
  to service_role, postgres;

do $$
declare
  existing_job bigint;
  scheduled_job bigint;
begin
  -- CI's disposable PostgreSQL service deliberately has no pg_cron. Production
  -- Supabase does; use only the supported cron functions when it is available.
  if to_regprocedure('cron.schedule(text,text,text)') is null
     or to_regprocedure('cron.unschedule(bigint)') is null then
    return;
  end if;

  for existing_job in
    execute 'select jobid from cron.job where jobname = $1'
      using 'dufynd-analytics-retention-v1'
  loop
    execute 'select cron.unschedule($1)' using existing_job;
  end loop;

  execute 'select cron.schedule($1, $2, $3)'
    into scheduled_job
    using
      'dufynd-analytics-retention-v1',
      '17 3 * * *',
      'select public.purge_dufynd_analytics_retention();';
end;
$$;
