-- Bounded operational metadata correction; no code, credential, cron, price or
-- task mutation. Run inside a transaction after the disposable regression.
-- Historical snapshots/cursors stay intact. New observers begin unverified and
-- must receive their first successful read from the existing GitHub poller.
do $reconcile$
declare
  old_id text;
  old_ids text[] := array[
    'github_pr:623', 'github_pr:625',
    'github_ci:37016647384', 'github_ci:37033948872'
  ];
  target record;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
  if not exists (
    select 1 from public.dufynd_external_observers
    where observer_id='github_branch:scentai-mvp'
      and last_snapshot->>'sha'='36cc84c34791284e4245ab4504ae020434dca89e'
  ) then
    raise exception 'production baseline changed; re-audit monitoring targets';
  end if;

  foreach old_id in array old_ids loop
    if exists (
      select 1 from public.dufynd_task_external_waits w
      join public.dufynd_autonomy_tasks t on t.task_id=w.task_id
      where w.observer_id=old_id
        and (not w.satisfied or t.status<>'done' or exists (
          select 1 from public.dufynd_execution_runs e
          where e.task_id=t.task_id and e.status not in ('completed','failed_terminal')
        ))
    ) then
      raise exception 'historical observer still has an active consumer';
    end if;
    if not exists (
      select 1 from public.dufynd_external_observers
      where observer_id=old_id and last_snapshot->>'state' in ('merged','success')
    ) then
      raise exception 'historical observer terminal proof missing';
    end if;
    update public.dufynd_external_observers
    set enabled=false, request_id=null, request_started_at=null,
        config=config||jsonb_build_object(
          'retirement_reason','terminal_observer_no_active_consumers',
          'retirement_audit','dufynd_ultra_20261028'
        )
    where observer_id=old_id and enabled;
  end loop;

  for target in select * from (values
    ('840',0), ('823',4), ('837',8), ('802',12)
  ) v(pr_number,delay_minutes) loop
    if exists (
      select 1 from public.dufynd_external_observers
      where observer_id='github_pr:'||target.pr_number
    ) then
      continue;
    end if;
    perform public.register_dufynd_observer(
      'github_pr',target.pr_number,
      '{"monitor_purpose":"release_readiness","registration_audit":"dufynd_ultra_20261028"}'::jsonb
    );
    -- Configure only a newly registered observer; reruns do not postpone it.
    update public.dufynd_external_observers
    set interval_seconds=1200,
        next_retry_at=now()+make_interval(mins=>target.delay_minutes)
    where observer_id='github_pr:'||target.pr_number
      and last_attempt_at is null and last_success_at is null
      and config->>'registration_audit'='dufynd_ultra_20261028';
  end loop;

  -- Correct a proven stale label without pretending to refresh the source.
  update public.dufynd_external_observers
  set health_status='stale',last_error='observer_success_stale'
  where observer_id='render:srv-dakpfrnf3r2c73dr3f20' and enabled
    and health_status in ('healthy','degraded')
    and coalesce(last_success_at,last_attempt_at,'-infinity'::timestamptz)
      < now()-make_interval(secs=>greatest(600,interval_seconds*3));
end;
$reconcile$;
