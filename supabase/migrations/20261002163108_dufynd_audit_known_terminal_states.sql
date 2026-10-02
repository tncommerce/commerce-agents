-- Align the audit vocabulary with the authoritative task constraint.
create or replace function public.dufynd_recovery_findings(t jsonb,e jsonb,observed_at timestamptz)
returns jsonb language sql stable security invoker set search_path=public as $$
select coalesce(jsonb_agg(reason order by reason),'[]') from (
 select 'unknown_state' reason where t is null or observed_at is null
  or coalesce(t->>'status','') not in ('planned','ready','in_progress','done','waiting_external','waiting_human_input','blocked','approval_required','cancelled')
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

