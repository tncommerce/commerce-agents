-- Execute with the migration in a transaction before deployment; always rollback.
begin;
do $$
declare b text:='phase2a_rollback_budget'; c text:='phase2a_rollback_fake';
 a uuid:=gen_random_uuid(); z uuid:=gen_random_uuid(); r jsonb; id uuid; s jsonb;
begin
 insert into public.dufynd_jarvis_budget_windows(budget_id,title,status,model,cap_usd,max_runs,reservation_enabled,reservation_dry_run)
 values(b,'rollback fake','active','fake',0.10,20,true,true);
 insert into public.dufynd_provider_contracts values(c,'fake',0.10,true,true,'{"type":"deterministic_fake"}',now()+interval '1 hour');
 insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,budget_class,worker_state,worker_owner,lease_token,lease_expires_at,heartbeat_at,last_progress_at,resource_scope)
 values('phase2a_rollback_a','test','fake','fake','in_progress','model','working','fake',a,now()+interval '1 hour',now(),now(),'["db:phase2a/a"]'),
 ('phase2a_rollback_b','test','fake','fake','in_progress','model','working','fake',z,now()+interval '1 hour',now(),now(),'["db:phase2a/b"]');
 r:=public.reserve_dufynd_model_call(b,'phase2a_rollback_a','fake',a,'one',repeat('a',64),c,0.10,180);
 if not (r->>'allowed')::boolean then raise exception 'exact boundary reservation rejected: %',r; end if;
 id:=(r->'reservation'->>'reservation_id')::uuid;
 r:=public.reserve_dufynd_model_call(b,'phase2a_rollback_a','fake',a,'one',repeat('a',64),c,0.10,180);
 if not (r->>'reused')::boolean or (select count(*) from public.dufynd_budget_reservations where budget_id=b)<>1 then raise exception 'duplicate reservation'; end if;
 r:=public.reserve_dufynd_model_call(b,'phase2a_rollback_b','fake',z,'two',repeat('a',64),c,0.10,180);
 if (r->>'allowed')::boolean then raise exception 'double spend admitted'; end if;
 if not public.dispatch_dufynd_model_call(id,a) or public.dispatch_dufynd_model_call(id,a) then raise exception 'dispatch fencing failed'; end if;
 if public.settle_dufynd_model_call(id,a,0.10001,'{"fake":true}') then raise exception 'bound overrun accepted'; end if;
 if not public.settle_dufynd_model_call(id,a,0.04,'{"fake":true}') then raise exception 'actual settlement failed'; end if;
 s:=public.get_dufynd_jarvis_budget_status(b);
 if (s->>'remaining_usd')::numeric<>0.06 or (s->>'reserved_unsettled_usd')::numeric<>0 then raise exception 'unused reserve not released: %',s; end if;
 -- Crash before dispatch releases; crash after dispatch charges the full bound.
 update public.dufynd_provider_contracts set max_call_usd=0.06 where contract_id=c;
 r:=public.reserve_dufynd_model_call(b,'phase2a_rollback_b','fake',z,'crash-unstarted',repeat('b',64),c,0.06,180);
 id:=(r->'reservation'->>'reservation_id')::uuid;
 update public.dufynd_budget_reservations set expires_at=now()-interval '1 second' where reservation_id=id;
 perform public.reconcile_dufynd_supervisor_v2();
 if (select status from public.dufynd_budget_reservations where reservation_id=id)<>'released' then raise exception 'undispatched TTL stuck'; end if;
 if public.dispatch_dufynd_model_call(id,z) then raise exception 'expired permit accepted'; end if;
 r:=public.reserve_dufynd_model_call(b,'phase2a_rollback_b','fake',z,'crash-started',repeat('c',64),c,0.06,180);
 id:=(r->'reservation'->>'reservation_id')::uuid;
 if not public.dispatch_dufynd_model_call(id,z) then raise exception 'second dispatch failed: %',r; end if;
 update public.dufynd_budget_reservations set expires_at=now()-interval '1 second' where reservation_id=id;
 perform public.reconcile_dufynd_supervisor_v2();
 if (select status from public.dufynd_budget_reservations where reservation_id=id)<>'charged_max' then raise exception 'ambiguous cost released unsafely'; end if;
 s:=public.get_dufynd_jarvis_budget_status(b);
 if (s->>'spent_usd')::numeric<>0.10 or (s->>'reserved_unsettled_usd')::numeric<>0 then raise exception 'crash cap accounting failed'; end if;
 if (public.reconcile_dufynd_budget_reservations()->>'reconciled')::int<>0 then raise exception 'TTL reconciliation not idempotent'; end if;
 if has_function_privilege('anon','public.reserve_dufynd_model_call(text,text,text,uuid,text,text,text,numeric,integer)','EXECUTE') then raise exception 'public reservation exposed'; end if;
 if has_function_privilege('authenticated','public.dispatch_dufynd_model_call(uuid,uuid)','EXECUTE') then raise exception 'public dispatch exposed'; end if;
end $$;
rollback;
