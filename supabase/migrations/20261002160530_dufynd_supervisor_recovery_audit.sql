-- Extend the certified state audit; no second recovery algorithm or handler.
create function public.dufynd_recovery_findings(t jsonb,e jsonb,observed_at timestamptz)
returns jsonb language sql stable security invoker set search_path=public as $$
select coalesce(jsonb_agg(reason order by reason),'[]') from (
 select 'unknown_state' reason where t is null or observed_at is null
  or coalesce(t->>'status','') not in ('planned','ready','in_progress','done','waiting_external','waiting_human_input','blocked')
  or coalesce(t->>'worker_state','') not in ('queued','ready','claimed','working','verifying','done','waiting_external','waiting_human_input','blocked','failed_retryable','failed_terminal','stale')
  or (e is not null and coalesce(e->>'status','') not in ('dispatch_pending','dispatched','running','verifying','completed','retryable','waiting_external','waiting_human','failed_terminal','stale'))
 union all select 'active_released_lease' where t->>'worker_state' in ('claimed','working','verifying') and t->>'released_at' is not null
 union all select 'expired_active_lease' where t->>'worker_state' in ('claimed','working','verifying') and t->>'released_at' is null
  and coalesce((t->>'lease_expires_at')::timestamptz,'-infinity')<=observed_at
 union all select 'stale_heartbeat' where t->>'worker_state' in ('working','verifying') and t->>'released_at' is null
  and coalesce((t->>'heartbeat_at')::timestamptz,'-infinity')<observed_at-interval '180 seconds'
 union all select 'progress_stalled' where t->>'worker_state' in ('working','verifying') and t->>'released_at' is null
  and coalesce((t->>'last_progress_at')::timestamptz,'-infinity')<observed_at-interval '600 seconds'
 union all select 'completed_execution_unreleased_lease' where e->>'status'='completed'
  and e->>'lease_token'=t->>'lease_token' and t->>'released_at' is null
 union all select 'done_task_running_execution' where t->>'status'='done' and e->>'status' in ('dispatched','running','verifying')
 union all select 'stale_fencing_token' where e->>'status' in ('dispatch_pending','dispatched','running','verifying','retryable','stale')
  and (e->>'lease_token' is null or e->>'lease_token' is distinct from t->>'lease_token')
 union all select 'retryable_without_owner' where e->>'status'='retryable'
  and (nullif(t->>'worker_owner','') is null or t->>'released_at' is not null or t->>'status'<>'in_progress')
) findings;
$$;

alter function public.read_dufynd_supervisor_audit() rename to read_dufynd_supervisor_audit_base;
create function public.read_dufynd_supervisor_audit() returns jsonb
language sql security invoker set search_path=public as $$
with findings as (
 select public.dufynd_recovery_findings(to_jsonb(t),to_jsonb(e),now()) reasons
 from public.dufynd_autonomy_tasks t left join public.dufynd_execution_runs e on e.task_id=t.task_id
 -- Old terminal executions may have a different fence from a new valid attempt.
 where t.lease_token is not null or e.execution_id is not null
), counts as (
 select reason,count(*) n from findings,jsonb_array_elements_text(reasons) reason group by reason
), dependencies as (
 select q.task_id,q.status,q.requires_human_approval,q.external_review_required,q.needs_freshness_recheck,
 case when jsonb_typeof(q.dependencies)='array' then not exists(
  select 1 from jsonb_array_elements_text(q.dependencies) d where not exists(
   select 1 from public.dufynd_autonomy_tasks x where x.task_id=d and x.status='done')) else false end internal_ready,
 not exists(select 1 from public.dufynd_task_external_waits w where w.task_id=q.task_id and (not w.satisfied or w.policy<>'dependency')) external_ready,
 (case when jsonb_typeof(q.dependencies)='array' then jsonb_array_length(q.dependencies)>0 else false end
  or exists(select 1 from public.dufynd_task_external_waits w where w.task_id=q.task_id)) registered,
 exists(select 1 from public.dufynd_execution_runs e where e.task_id=q.task_id and e.status not in ('completed','failed_terminal')) executing
 from public.dufynd_autonomy_tasks q where q.status in ('waiting_external','blocked','ready')
)
select public.read_dufynd_supervisor_audit_base()||jsonb_build_object(
 'extension_revision',2,'recovery_consistency',jsonb_build_object(
  'healthy',not exists(select 1 from counts),'reason_counts',(select coalesce(jsonb_object_agg(reason,n),'{}') from counts),
  'repair_performed',false),
 'dependency_readiness',jsonb_build_object(
  'waiting_but_eligible',(select count(*) from dependencies where status in ('waiting_external','blocked') and internal_ready and external_ready and registered and not executing and not requires_human_approval and not external_review_required and not needs_freshness_recheck),
  'ready_missing_dependency',(select count(*) from dependencies where status='ready' and (not internal_ready or not external_ready)),
  'state_mutated',false),
 'unknown_state_fail_closed',true);
$$;

revoke all on function public.dufynd_recovery_findings(jsonb,jsonb,timestamptz),
 public.read_dufynd_supervisor_audit_base(),public.read_dufynd_supervisor_audit() from public,anon,authenticated;
grant execute on function public.dufynd_recovery_findings(jsonb,jsonb,timestamptz),
 public.read_dufynd_supervisor_audit_base(),public.read_dufynd_supervisor_audit() to service_role;
