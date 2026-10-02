-- Run in one transaction against the actual migrated schema; always roll back.
-- No model calls, live catalog writes, or durable test tasks.
begin;
do $$
declare a uuid:=gen_random_uuid(); b uuid:=gen_random_uuid(); result jsonb; h timestamptz;
begin
 insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,resource_scope,budget_class)
 values ('v2_test_a','test','A','test','ready','["repo:tests/a"]','free'),
 ('v2_test_b','test','B','test','ready','["repo:tests/a/nested"]','free'),
 ('v2_test_c','test','C','test','ready','["repo:tests/c"]','free');
 result:=public.claim_dufynd_worker_v2('v2_test_a','test-a',a);
 if result is null then raise exception 'first claim failed'; end if;
 if public.claim_dufynd_worker_v2('v2_test_b','test-b',b) is not null then raise exception 'scope collision accepted'; end if;
 if public.claim_dufynd_worker_v2('v2_test_c','test-c',b) is null then raise exception 'disjoint claim denied'; end if;
 if public.update_dufynd_worker_v2('v2_test_a',b,'heartbeat') then raise exception 'foreign token accepted'; end if;
 select last_progress_at into h from public.dufynd_autonomy_tasks where task_id='v2_test_a';
 perform public.update_dufynd_worker_v2('v2_test_a',a,'heartbeat');
 if (select last_progress_at from public.dufynd_autonomy_tasks where task_id='v2_test_a')<>h then raise exception 'heartbeat faked progress'; end if;
 -- Test stalled progress with a fresh heartbeat under a controlled fixture write.
 perform set_config('dufynd.worker_write','supervisor',true);
 update public.dufynd_autonomy_tasks set last_progress_at=now()-interval '601 seconds' where task_id='v2_test_a';
 perform set_config('dufynd.worker_write','',true);
 perform public.reconcile_dufynd_supervisor_v2();
 if (select worker_state from public.dufynd_autonomy_tasks where task_id='v2_test_a')<>'failed_retryable' then raise exception 'progress stall not recovered'; end if;
 if public.update_dufynd_worker_v2('v2_test_a',a,'done','old worker') then raise exception 'stale token accepted'; end if;
 result:=public.claim_dufynd_worker_v2('v2_test_a','test-retry',gen_random_uuid());
 if result is null then raise exception 'expired lease not reclaimable'; end if;
 a:=(result->>'lease_token')::uuid;
 perform public.update_dufynd_worker_v2('v2_test_a',a,'waiting_human_input','budget ran out','budget_exhausted');
 if (select status from public.dufynd_autonomy_tasks where task_id='v2_test_a')='waiting_human_input' then raise exception 'budget escalated to human'; end if;
 result:=public.claim_dufynd_worker_v2('v2_test_a','test-human',gen_random_uuid());
 a:=(result->>'lease_token')::uuid;
 perform public.update_dufynd_worker_v2('v2_test_a',a,'waiting_human_input','owner decision required','owner_decision');
 if (select status from public.dufynd_autonomy_tasks where task_id='v2_test_a')<>'waiting_human_input' then raise exception 'real human gate rejected'; end if;
 perform public.update_dufynd_worker_v2('v2_test_c',b,'verifying','deterministic assertions passed');
 perform public.update_dufynd_worker_v2('v2_test_c',b,'done','verified SQL test evidence');
 if (select released_at from public.dufynd_autonomy_tasks where task_id='v2_test_c') is null then raise exception 'terminal lease not released'; end if;
 insert into public.dufynd_master_status(key,category,value,priority)
 values('continuity.tech_lease','tech',jsonb_build_object('status','active','released_at',now(),'expires_at',now()+interval '1 hour'),100)
 on conflict(key) do update set value=excluded.value;
 if (select value->>'status' from public.dufynd_master_status where key='continuity.tech_lease')='active' then raise exception 'released lease considered active'; end if;
 if has_function_privilege('anon','public.claim_dufynd_worker_v2(text,text,uuid)','EXECUTE') then raise exception 'public claim exposed'; end if;
 if has_function_privilege('authenticated','public.reconcile_dufynd_supervisor_v2()','EXECUTE') then raise exception 'public recovery exposed'; end if;
end $$;
rollback;
