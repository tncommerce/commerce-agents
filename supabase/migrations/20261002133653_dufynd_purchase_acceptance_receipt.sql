-- Project the fourth exact acceptance receipt through the existing watchdog.
-- Bounded receipt projection inside the existing watchdog; no queue or new poll.
create or replace function public.project_dufynd_acceptance_receipts() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare m public.dufynd_master_status; e public.dufynd_execution_runs; t public.dufynd_autonomy_tasks;
 verified boolean; destination text; receipt jsonb; changed int:=0;
begin
 for m in select * from public.dufynd_master_status where key in
 ('jarvis.external_observer.acceptance','jarvis.capability_packet.acceptance','jarvis.state_audit.acceptance','jarvis.purchase_freshness.acceptance') for update loop
  select * into e from public.dufynd_execution_runs where task_id=m.value->>'task_id'
   and (nullif(m.value->>'execution_id','') is null or execution_id::text=m.value->>'execution_id')
   order by created_at desc limit 1;
  if not found or coalesce(e.handler_id,e.payload->>'kind') not in ('durability_probe','supervisor_state_audit','purchase_destination_freshness_audit') then continue; end if;
  select * into t from public.dufynd_autonomy_tasks where task_id=e.task_id;
  verified:=e.status='completed' and e.last_checkpoint->>'verified'='true'
    and t.status='done' and t.released_at is not null and t.budget_class='free';
  destination:=case when verified then case when m.value->>'status'='live_accepted' then 'live_accepted' else 'live_execution_verified' end
    when e.status='completed' and t.status='blocked' then 'execution_review_required'
    when e.status='failed_terminal' then 'execution_failed_terminal'
    when e.status in ('retryable','stale') then 'execution_recovery_pending'
    else 'execution_in_progress' end;
  -- Full phase acceptance (CI, deploy, source-event proof) is never fabricated here.
  receipt:=jsonb_build_object('receipt_version',1,'execution_id',e.execution_id,'task_id',e.task_id,
   'execution_status',e.status,'execution_verified',coalesce(verified,false),
   'worker_type',e.worker_type,'external_run_id',e.external_run_id,
   'handler_id',coalesce(e.handler_id,e.payload->>'kind'),'handler_version',e.handler_version,
   'packet_version',e.task_packet->'packet_version','packet_hash',e.packet_hash,
   'checkpoint_step',e.last_checkpoint->'step','checkpoint_verified',e.last_checkpoint->'verified',
   'report_hash',e.last_checkpoint->'audit_hash','completed_at',e.completed_at,
   'lease_released',t.released_at is not null,
   'dispatch_count',(select count(*) from jsonb_array_elements(e.evidence) v where v->>'event' in ('external_dispatch_bound','certified_supervisor_dispatch')),
   'source','persistent_execution_ledger','ci_acceptance_inferred',false);
  if m.value->'execution_receipt' is distinct from receipt or m.value->>'status' is distinct from destination then
   update public.dufynd_master_status set value=value||jsonb_build_object('status',destination,'execution_receipt',receipt),last_verified_at=now() where key=m.key;
   changed:=changed+1;
  end if;
 end loop;
 return jsonb_build_object('projected',changed);
end $$;
