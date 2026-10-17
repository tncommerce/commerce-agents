-- DUFYND supervisor: prevent shared internal purchase observer replay from
-- rearming historical, already-completed purchase-verification tasks.
-- Scope: existing event processor only; no new worker, cron, provider or queue.
-- Live evidence 2026-10-17: four released purchase-freshness tasks have completed
-- execution receipts but were placed back in status=ready after newer due events.
-- SQL contract is fetched from current existing function; only 3 bounded guards.
--
-- Must be merged/migrated only after separate owner production approval.
-- Changes below are NOT applied to production by this draft PR.

CREATE OR REPLACE FUNCTION public.process_dufynd_external_events()
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
declare ev public.dufynd_jarvis_inbox; w record; t public.dufynd_autonomy_tasks; affected int:=0; processed int:=0; kind text; matched boolean; ready boolean; prepared jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 perform set_config('dufynd.event_processing','true',true);
 perform set_config('dufynd.worker_write','supervisor',true);
 for ev in select * from public.dufynd_jarvis_inbox where fingerprint is not null and status='pending' order by inbox_id limit 100 for update skip locked loop
  for w in select * from public.dufynd_task_external_waits as wait_row
  where wait_row.observer_id=ev.payload->>'observer_id'
    and (
      ev.source_type is distinct from 'internal_dependency'
      or (jsonb_typeof(ev.related_task_ids) = 'array'
          and ev.related_task_ids ? wait_row.task_id)
    ) loop
   select * into t from public.dufynd_autonomy_tasks where task_id=w.task_id for update;
   if t.status in ('done','cancelled','in_progress')
    or (t.durable_payload->>'kind'='purchase_destination_freshness_audit'
        and t.released_at is not null)
    or exists(select 1 from public.dufynd_execution_runs
      where task_id=t.task_id and status not in ('completed','failed_terminal'))
   then continue; end if;
   kind:=ev.event_type; matched:=w.event_types ? kind and (w.expected_sha is null or w.expected_sha=ev.payload->'evidence'->>'sha');
   if matched then
    update public.dufynd_task_external_waits set satisfied=true,last_event_id=ev.event_id,reevaluated_at=now() where task_id=w.task_id and observer_id=w.observer_id;
    if w.policy='review' then
     update public.dufynd_autonomy_tasks set external_review_required=true,blocked_reason='external_response_review',
      status=case when requires_human_approval then status else 'ready' end,worker_state=case when requires_human_approval then worker_state else 'queued' end,
      evidence=right(coalesce(evidence,'')||E'\nObserved reply/delivery event; review required; no rights or publication approval inferred. Event '||ev.event_id::text,12000) where task_id=t.task_id;
    elsif w.policy='freshness' then
     update public.dufynd_task_external_waits set satisfied=false where task_id=t.task_id and policy='dependency';
     update public.dufynd_autonomy_tasks set needs_freshness_recheck=true,blocked_reason='freshness_recheck',status='waiting_external',worker_state='waiting_external' where task_id=t.task_id and not requires_human_approval;
    end if;
   elsif kind in ('github.ci.failure','github.workflow.failure','render.deployment.failed') and (w.expected_sha is null or w.expected_sha=ev.payload->'evidence'->>'sha') then
    update public.dufynd_task_external_waits set satisfied=false,last_event_id=ev.event_id,reevaluated_at=now() where task_id=w.task_id and observer_id=w.observer_id;
    update public.dufynd_autonomy_tasks set blocked_reason='external_failure_retryable',worker_state='failed_retryable',status='waiting_external' where task_id=t.task_id and not requires_human_approval;
   end if;
   update public.dufynd_autonomy_tasks set last_external_event_id=ev.event_id,evidence=right(coalesce(evidence,'')||E'\nExternal event '||ev.event_id::text||' '||ev.event_type,12000) where task_id=t.task_id;
   affected:=affected+1;
  end loop;
  if ev.source_type='internal_dependency' then
   update public.dufynd_autonomy_tasks set last_external_event_id=ev.event_id where dependencies ? ev.source_id and status in ('waiting_external','blocked')
    and not exists(select 1 from public.dufynd_execution_runs where task_id=dufynd_autonomy_tasks.task_id and status not in ('completed','failed_terminal'));
  end if;
  update public.dufynd_jarvis_inbox set status='done',processed_at=now(),attempts=attempts+1 where inbox_id=ev.inbox_id; processed:=processed+1;
 end loop;
 -- Only registered waiters with all external AND exact internal dependencies satisfied.
 for t in select * from public.dufynd_autonomy_tasks q where q.status in ('waiting_external','blocked','ready')
  and not q.requires_human_approval and not q.external_review_required and not q.needs_freshness_recheck
  and not (q.durable_payload->>'kind'='purchase_destination_freshness_audit'
    and q.released_at is not null)
  and (exists(select 1 from public.dufynd_task_external_waits where task_id=q.task_id) or (jsonb_typeof(q.dependencies)='array' and jsonb_array_length(q.dependencies)>0))
  and not exists(select 1 from public.dufynd_task_external_waits where task_id=q.task_id and (not satisfied or policy<>'dependency'))
  and jsonb_typeof(q.dependencies)='array' and not exists(select 1 from jsonb_array_elements_text(q.dependencies) d where not exists(select 1 from public.dufynd_autonomy_tasks x where x.task_id=d and x.status='done'))
  and not exists(select 1 from public.dufynd_execution_runs where task_id=q.task_id and status not in ('completed','failed_terminal')) for update loop
  update public.dufynd_autonomy_tasks set status='ready',worker_state='ready',blocked_reason=null,evidence=right(coalesce(evidence,'')||E'\nDeterministic dependency reevaluation: ready.',12000) where task_id=t.task_id and (status<>'ready' or worker_state<>'ready' or blocked_reason is not null);
  -- No improvised handler, no paid fallback. Existing registry validates payload.
  if t.budget_class='free' and t.durable_payload is not null and t.durability_policy='durable' then
   prepared:=public.prepare_dufynd_execution(t.task_id,'event-wake:'||t.task_id,t.domain,t.resource_scope,t.durable_payload,'durable');
   -- prepare RPC resets its token context; restore for subsequent task/event writes.
   perform set_config('dufynd.worker_write','supervisor',true);
  end if;
 end loop;
 perform set_config('dufynd.worker_write','',true);
 perform set_config('dufynd.event_processing','',true);
 return jsonb_build_object('processed',processed,'affected',affected);
end $function$;
 
-- Preserve current service-only execution boundary after replacing the function.
revoke all on function public.process_dufynd_external_events()
  from public, anon, authenticated;
grant execute on function public.process_dufynd_external_events()
  to service_role, postgres;

-- One-time, idempotent repair of *already released and completed* purchase
-- attempts. Do not forge a successful merchant observation: cancelled means an
-- obsolete task generation, not a safe_evidence_refresh or a sale.
-- Future due periods always receive a NEW cryptographically bound task_id from
-- the already existing wake_dufynd_purchase_freshness() implementation.
update public.dufynd_autonomy_tasks t
set status='cancelled',
    worker_state='done',
    blocked_reason='superseded_completed_purchase_attempt',
    evidence=right(coalesce(t.evidence,'') ||
      E'\nReconciled stale ready state after terminal purchase execution; ' ||
      'merchant proof remains exclusively in durable execution/evidence.', 12000)
where t.status='ready'
  and t.worker_state='ready'
  and t.released_at is not null
  and t.durable_payload->>'kind'='purchase_destination_freshness_audit'
  and exists (
    select 1 from public.dufynd_execution_runs e
    where e.task_id=t.task_id and e.status='completed'
      and e.completed_at is not null
  )
  and not exists (
    select 1 from public.dufynd_execution_runs e
    where e.task_id=t.task_id
      and e.status not in ('completed','failed_terminal')
  );

-- No direct merchant/affiliate, price, target certification, production branch,
-- scheduler, analytics, credential or social record is changed.
