-- Preserve existing due-event routing and merchant verification evidence.
create or replace function public.wake_dufynd_purchase_freshness() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare v public.dufynd_purchase_verification_targets; tid text; oid text; payload jsonb; fp text; n int:=0;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 for v in select * from public.dufynd_purchase_verification_targets
 where (enabled or certification_due) and (retry_after is null or retry_after<=now())
 and (certification_due or last_verified_at+make_interval(hours=>max_age_hours-safety_window_hours)<=now())
 and (last_result is null or last_result->>'decision' in ('safe_evidence_refresh','transport_unverified')) for update loop
  tid:=case when v.certification_due then 'purchase_freshness_acceptance_20261002'
   else 'purchase-freshness:'||substr(encode(sha256(convert_to(v.offer_id||':'||v.last_verified_at::text||':'||coalesce(v.retry_after::text,''),'UTF8')),'hex'),1,32) end;
  oid:=public.register_dufynd_observer('internal_dependency','purchase-freshness:'||v.offer_id);
  payload:=jsonb_build_object('kind','purchase_destination_freshness_audit','steps',1,'interval_seconds',2,
   'offer_id',v.offer_id,'product_id',v.product_id,'canonical_identity',v.canonical_identity,'offer_contract',v.offer_contract,
   'last_verified_at',v.last_verified_at,'expiry',v.last_verified_at+make_interval(hours=>v.max_age_hours),
   'verification_contract','perfumetrader_exact_html_v1','allowed_mutations',jsonb_build_array('verification_evidence'));
  insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,budget_class,durability_policy,resource_scope,durable_payload,required_capabilities,forbidden_actions)
  values(tid,'supervisor','Exact purchase evidence verification','Verify the compiled merchant contract only; no business mutations.','waiting_external','free','durable',
   jsonb_build_array('db:purchase-evidence:'||v.offer_id),payload,
   '["commerce.evidence.write","commerce.read","commerce.verify_exact","supabase.execution_state","supabase.task_state"]',
   '["gmail.send","social.publish","budget.spend","main.merge","commerce.activate","shell.execute"]') on conflict do nothing;
  perform public.bind_dufynd_external_wait(tid,oid,'["purchase.freshness.due"]');
  fp:=encode(sha256(convert_to('purchase.freshness.due:'||tid,'UTF8')),'hex');
  insert into public.dufynd_jarvis_inbox(event_type,source_type,source_id,payload,fingerprint,related_task_ids)
  values('purchase.freshness.due','internal_dependency',v.offer_id,
   jsonb_build_object('observer_id',oid,'evidence',jsonb_build_object('offer_id',v.offer_id,'expiry',payload->'expiry','wake_reason',case when v.certification_due then 'initial_certification' else 'pre_expiry' end)),fp,jsonb_build_array(tid))
   on conflict(fingerprint) where fingerprint is not null do nothing;
  if found then n:=n+1; end if;
 end loop;
 -- This is a scheduler observation, not a merchant verification.
 -- Only the already registered purchase-target dependencies are eligible.
 update public.dufynd_external_observers o
 set last_attempt_at=now(), last_success_at=now(), consecutive_failures=0,
     health_status=case when t.enabled or t.certification_due then 'healthy' else 'blocked_configuration' end,
     last_error=case when t.enabled or t.certification_due then null else 'purchase_target_disabled' end,
     next_retry_at=now()+make_interval(secs=>greatest(30,least(o.interval_seconds,600))),
     last_snapshot=jsonb_build_object('monitor_basis','purchase_target_scheduler',
       'checked_at',now(),'offer_id',t.offer_id,'last_verified_at',t.last_verified_at,
       'verification_due_at',t.last_verified_at+make_interval(hours=>t.max_age_hours-t.safety_window_hours),
       'retry_after',t.retry_after,'certification_due',t.certification_due)
 from public.dufynd_purchase_verification_targets t
 where o.source_type='internal_dependency' and o.source_id='purchase-freshness:'||t.offer_id and o.enabled;
 update public.dufynd_external_observers o
 set last_attempt_at=now(),health_status='blocked_configuration',last_error='purchase_target_missing',
     next_retry_at=now()+interval '10 minutes'
 where o.source_type='internal_dependency' and o.source_id like 'purchase-freshness:%' and o.enabled
 and not exists(select 1 from public.dufynd_purchase_verification_targets t
   where o.source_id='purchase-freshness:'||t.offer_id);
 return jsonb_build_object('wake_events',n);
end $$;

