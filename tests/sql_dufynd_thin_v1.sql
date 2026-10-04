-- Real migrated-schema assertions; all fixtures and HTTP requests roll back.
begin;
do $$
declare report jsonb; eid uuid; n int; gate text;
begin
 update public.dufynd_master_status set value='{"enabled":false}' where key='jarvis.thin_v1.config';
 if public.run_dufynd_thin_v1()->>'stop_reason'<>'disabled' then raise exception 'bootstrap not disabled'; end if;
 update public.dufynd_master_status set value='{"enabled":true}' where key='jarvis.thin_v1.config';
 update public.dufynd_external_observers set enabled=true,health_status='healthy',last_success_at=now(),last_snapshot='{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}' where observer_id='github_branch:scentai-mvp';
 insert into public.dufynd_master_status(key,category,value)
 values('jarvis.thin_v1.ci','jarvis',jsonb_build_object('sha',repeat('a',40),'ready',true,'checked_at',now(),'next_poll_at',now()+interval '10 minutes','run_id','123'))
 on conflict(key) do update set value=excluded.value;
 insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,priority,budget_class,resource_scope,durability_policy,durable_payload,dependencies)
 values('thin_test_a','supervisor','A','Exact free audit','ready',100,'free','["db:jarvis.supervisor_v2.health"]','durable','{"kind":"supervisor_state_audit","steps":1,"interval_seconds":2}','[]'),
 ('thin_test_b','supervisor','B','Exact free audit','ready',100,'free','["db:jarvis.supervisor_v2.health"]','durable','{"kind":"supervisor_state_audit","steps":1,"interval_seconds":2}','["thin_test_a"]'),
 ('thin_test_missing','supervisor','Missing','Exact free audit','ready',100,'free','["db:jarvis.supervisor_v2.health"]','durable','{"kind":"supervisor_state_audit","steps":1,"interval_seconds":2}','["missing_dependency"]');
 insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,budget_class,resource_scope)
 values('thin_test_holder','test','Holder','Scope fixture','ready','free','["db:jarvis.supervisor_v2.health"]');
 report:=public.claim_dufynd_worker_v2('thin_test_holder','test-holder',gen_random_uuid());
 if report is null then raise exception 'fixture claim failed'; end if;
 perform public.run_dufynd_thin_v1();
 if exists(select 1 from public.dufynd_execution_runs where task_id in ('thin_test_a','thin_test_b')) then raise exception 'resource conflict ignored'; end if;
 perform public.update_dufynd_worker_v2('thin_test_holder',(report->>'lease_token')::uuid,'verifying','scope fixture verified');
 perform public.update_dufynd_worker_v2('thin_test_holder',(report->>'lease_token')::uuid,'done','scope fixture verified');
 report:=public.run_dufynd_thin_v1();
 if (select count(*) from public.dufynd_autonomy_tasks where task_id in ('thin_test_a','thin_test_b') and status='done' and released_at is not null)<>2 then raise exception 'automatic successor did not complete'; end if;
 if (select status from public.dufynd_autonomy_tasks where task_id='thin_test_missing')<>'ready' then raise exception 'missing dependency executed'; end if;
 select execution_id into eid from public.dufynd_execution_runs where task_id='thin_test_a';
 if (select status from public.dufynd_execution_runs where execution_id=eid)<>'completed' then raise exception 'execution not terminal'; end if;
 if not exists(select 1 from public.dufynd_execution_runs e,jsonb_array_elements(e.evidence) v where e.execution_id=eid and v->>'event'='verified_completed') then raise exception 'verified evidence absent'; end if;
 -- Same queued task/slot is never re-executed.
 select count(*) into n from public.dufynd_execution_runs;
 perform public.run_dufynd_thin_v1();
 if (select count(*) from public.dufynd_execution_runs)<>n then raise exception 'idempotency failed'; end if;
 insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,priority,budget_class,resource_scope,approval_action_type)
 values('thin_test_gate','content','Publish','Must not execute','ready',100,'free','["db:test-gate"]','social.publish');
 report:=public.run_dufynd_thin_v1();
 if report->>'stop_reason'<>'owner_gate' or (select status from public.dufynd_autonomy_tasks where task_id='thin_test_gate')<>'ready' then raise exception 'gate executed'; end if;
 if not exists(select 1 from public.dufynd_human_decisions where context->>'task_id'='thin_test_gate' and status='pending' and context->>'exact_go_answer'=decision_token and context->>'gate_action_executed'='false') then raise exception 'gate signal incomplete'; end if;
 select count(*) into n from public.dufynd_human_decisions where context->>'task_id'='thin_test_gate';
 perform public.run_dufynd_thin_v1();
 if (select count(*) from public.dufynd_human_decisions where context->>'task_id'='thin_test_gate')<>n then raise exception 'duplicate decision'; end if;
 for gate in select unnest(array['social.publish','budget.spend','commerce.activate','external.outreach','main.merge','credentials','destructive','irreversible']) loop
  if public.dufynd_thin_gate(jsonb_build_object('budget_class','free','provider_cost_unknown',false,'required_capabilities',jsonb_build_array(gate))) is null then raise exception 'unsafe capability accepted: %',gate; end if;
 end loop;
 if public.dufynd_thin_gate('{"budget_class":"model","provider_cost_unknown":false}')<>'paid_model_call' then raise exception 'paid task accepted'; end if;
 -- Failed/stale/head-mismatched CI cannot consume even a safe task.
 update public.dufynd_master_status set value=value||'{"ready":false}' where key='jarvis.thin_v1.ci';
 if public.run_dufynd_thin_v1()->>'stop_reason'<>'waiting_external' then raise exception 'non-green CI accepted'; end if;
 update public.dufynd_master_status set value=value||jsonb_build_object('ready',true,'checked_at',now()-interval '21 minutes') where key='jarvis.thin_v1.ci';
 if public.run_dufynd_thin_v1()->>'stop_reason'<>'waiting_external' then raise exception 'stale CI accepted'; end if;
 update public.dufynd_external_observers set last_success_at=now()-interval '11 minutes' where observer_id='github_branch:scentai-mvp';
 if public.run_dufynd_thin_v1()->>'stop_reason'<>'waiting_external' then raise exception 'stale HEAD accepted'; end if;
 update public.dufynd_external_observers set last_success_at=now(),last_snapshot=jsonb_build_object('sha',repeat('b',40)) where observer_id='github_branch:scentai-mvp';
 if public.run_dufynd_thin_v1()->>'stop_reason'<>'waiting_external' then raise exception 'moved HEAD accepted'; end if;
 if has_function_privilege('anon','public.run_dufynd_thin_v1()','execute') or has_function_privilege('authenticated','public.poll_dufynd_thin_ci()','execute') then raise exception 'public orchestration exposed'; end if;
end $$;
rollback;
