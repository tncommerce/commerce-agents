-- Operational reconciliation for already merged PRs 823 and 840.
-- No task, event, cursor, source snapshot, credential or schedule is changed.
-- The guards are evaluated atomically under the existing supervisor lock.
do $retire$
declare
  target record;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
  if not exists (
    select 1 from public.dufynd_external_observers
    where observer_id='github_branch:scentai-mvp'
      and last_snapshot->>'sha'='760d3a352b2b344e6a9b75abb69b576af1f84d19'
  ) then
    raise exception 'production baseline changed; re-audit retirement';
  end if;

  for target in select * from (values
    ('823','a9a8220d503d7db2bacfe1f4319188ca813878fa'),
    ('840','833feefcd6e4c525ef83fcd0a3a3f9f9b72629f3')
  ) v(pr_number,head_sha) loop
    perform 1 from public.dufynd_external_observers
    where observer_id='github_pr:'||target.pr_number for update;
    if not exists (
      select 1 from public.dufynd_external_observers
      where observer_id='github_pr:'||target.pr_number
        and source_type='github_pr' and source_id=target.pr_number
        and last_snapshot->>'state'='merged'
        and last_snapshot->>'sha'=target.head_sha
        and last_snapshot->>'base_ref'='scentai-mvp'
        and last_snapshot->>'merge_commit_sha'='89aae8925e606caa33f8f7dafa3edbeafab32c3c'
        and last_success_at between now()-interval '2 hours' and now()
        and request_id is null and request_started_at is null
    ) then
      raise exception 'terminal observer proof changed or request pending';
    end if;
    if exists (
      select 1 from public.dufynd_task_external_waits w
      join public.dufynd_autonomy_tasks t on t.task_id=w.task_id
      where w.observer_id='github_pr:'||target.pr_number
        and (not w.satisfied or t.status<>'done' or exists (
          select 1 from public.dufynd_execution_runs e
          where e.task_id=t.task_id and e.status not in ('completed','failed_terminal')
        ))
    ) or exists (
      select 1 from public.dufynd_autonomy_tasks t
      where t.durable_payload->>'pr_number'=target.pr_number
    ) or exists (
      select 1 from public.dufynd_execution_runs e
      where e.payload->>'pr_number'=target.pr_number
        or e.task_packet->'payload'->>'pr_number'=target.pr_number
    ) then
      raise exception 'terminal observer still has a consumer';
    end if;

    update public.dufynd_external_observers
    set enabled=false,
      config=config||jsonb_build_object(
        'retired_at',now(),
        'retirement_reason','terminal_observer_no_active_consumers',
        'retirement_audit','dufynd_scheduler_monitoring_20261029'
      )
    where observer_id='github_pr:'||target.pr_number and enabled;
  end loop;
end;
$retire$;
