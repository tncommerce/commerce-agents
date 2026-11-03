-- Disposable database only. All fixture data and replaced functions roll back.
begin;
set local statement_timeout='20000ms';
select set_config('dufynd.worker_write','supervisor',true);
create temp table business_dedupe_cases(key text primary key,value jsonb) on commit drop;
create temp table business_dedupe_results(label text primary key) on commit drop;
create function pg_temp.dedupe_assert(ok boolean,label text) returns void language plpgsql as $$
begin
 if ok is distinct from true then raise exception 'FAIL: %',label; end if;
 insert into business_dedupe_results values(label);
end $$;
insert into business_dedupe_cases values
('queue','{"state":"planner_gap"}'),
('fm','{"content_id":"dedupe-fixture","experiment_id":"dedupe-campaign","publication_verified":false,"observed_at":"2026-10-01T00:00:00Z","phase":"prelaunch","next_evidence":"publication_evidence","schedule":{"instagram":"2026-10-01T09:00:00Z"},"funnel":{"landing_sessions":0},"recent_signals":[],"purchase_evidence":{"offer_id":"fixture-offer","product_id":"fixture-product","enabled":true,"decision":"verified","stock":"in_stock","price_eur":71.9,"last_verified_at":"2026-10-01T00:00:00Z"}}');
create or replace function public.get_dufynd_next_autonomous_action()
returns jsonb language sql stable set search_path to 'public' as $$
 select value from pg_temp.business_dedupe_cases where key='queue'
$$;
create or replace function public.read_dufynd_first_money_runtime()
returns jsonb language sql stable set search_path to 'public' as $$
 select value from pg_temp.business_dedupe_cases where key='fm'
$$;
delete from public.dufynd_master_status where key='jarvis.business_source_dedupe_v1';
insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status)
values('bizplan:creative-recovery:'||to_char(now() at time zone 'UTC','YYYYMMDD'),
 'content','fixture completed content','fixture only','done')
on conflict(task_id) do update set status='done';

do $test$
declare r jsonb; saved jsonb; base_count bigint; after_count bigint; first_id text;
begin
 select count(*) into base_count from public.dufynd_autonomy_tasks;
 r:=public.plan_dufynd_autonomous_business_work_v1();
 first_id:=r->'created_tasks'->>0;
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=1,'01 initial bounded audit');
 perform pg_temp.dedupe_assert((select durable_payload='{"kind":"supervisor_state_audit","steps":1,"interval_seconds":2}'::jsonb and budget_class='free' and not requires_human_approval from public.dufynd_autonomy_tasks where task_id=first_id),'02 certified payload unchanged');
 select to_jsonb(m) into saved from public.dufynd_master_status m where key='jarvis.business_source_dedupe_v1';
 update public.dufynd_autonomy_tasks set status='done' where task_id=first_id;
 for i in 1..24 loop
  update business_dedupe_cases set value=value||jsonb_build_object('observed_at',now()+i*interval '1 hour','phase','post_measurement_window','next_evidence','qualified_session') where key='fm';
  r:=public.plan_dufynd_autonomous_business_work_v1();
  if jsonb_array_length(r->'created_tasks')<>0 then raise exception 'unchanged source requeued on poll %',i; end if;
 end loop;
 perform pg_temp.dedupe_assert(r->>'source_unchanged'='true','03 24 clock-only polls create zero audits');
 perform pg_temp.dedupe_assert((select to_jsonb(m)=saved from public.dufynd_master_status m where key='jarvis.business_source_dedupe_v1'),'04 unchanged checkpoint is not rewritten');
 perform pg_temp.dedupe_assert((select status='done' from public.dufynd_autonomy_tasks where task_id=first_id),'05 completed audit never reset');

 update business_dedupe_cases set value=jsonb_set(jsonb_set(value,'{funnel,landing_sessions}','1'),'{recent_signals}','[{"event_id":"buyer-1","event":"page_view","occurred_at":"2026-10-02T09:00:00Z"}]') where key='fm';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=1,'06 actual buyer event creates audit');
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=0,'07 buyer event replay deduplicated');
 update business_dedupe_cases set value=jsonb_set(value,'{purchase_evidence,last_verified_at}','"2026-10-26T09:00:00Z"') where key='fm';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=0,'08 identical merchant refresh is not a business event');
 update business_dedupe_cases set value=jsonb_set(value,'{purchase_evidence,price_eur}','72.9') where key='fm';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=1,'09 merchant price change creates audit');
 update business_dedupe_cases set value=jsonb_set(value,'{purchase_evidence,price_eur}','71.9') where key='fm';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=1,'10 genuine A B A source transition is processed');

 insert into public.dufynd_content_assets(id,content_id,platform,status)
 values('dedupe-fixture-asset','dedupe-fixture','instagram','draft');
 insert into public.dufynd_content_workflows(asset_id,state,revision_fingerprint,evidence)
 values('dedupe-fixture-asset','published',repeat('a',64),'{"publication_observation":{"status":"pass","platform_post_id":"post-1","observed_at":"2026-10-01T00:00:00Z"}}');
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=1,'11 original publication proof creates audit');
 update public.dufynd_content_workflows set state='measurement_active',last_progress_at=now(),evidence=jsonb_set(evidence,'{publication_observation,observed_at}','"2026-10-26T00:00:00Z"') where asset_id='dedupe-fixture-asset';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=0,'12 workflow bookkeeping and proof polling do not requeue');
 perform pg_temp.dedupe_assert(public.read_dufynd_first_money_runtime()->>'publication_verified'='false','13 no fabricated publication verification');

 insert into public.dufynd_master_status(key,category,value)
 values('jarvis.thin_v1.first_money_schedule_observation','jarvis','{"content_id":"dedupe-fixture","experiment_id":"dedupe-campaign","posts":[{"id":"post-2","platform":"tiktok","status":"PENDING"}]}')
 on conflict(key) do update set value=excluded.value;
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=1,'14 matching platform schedule source processed');
 update public.dufynd_master_status set value=jsonb_set(value,'{posts,0,status}','"PUBLISHED"') where key='jarvis.thin_v1.first_money_schedule_observation';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=1,'15 original platform publication transition processed');
 update public.dufynd_master_status set value=value||jsonb_build_object('observed_at',now()) where key='jarvis.thin_v1.first_money_schedule_observation';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=0,'16 repeated platform poll deduplicated');

 select count(*) into after_count from public.dufynd_autonomy_tasks;
 update business_dedupe_cases set value='{"state":"owner_gate"}' where key='queue';
 update business_dedupe_cases set value=jsonb_set(value,'{purchase_evidence,stock}','"out_of_stock"') where key='fm';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(r->>'state'='owner_gate' and jsonb_array_length(r->'created_tasks')=0,'17 owner gate wins over new source');
 update business_dedupe_cases set value='{"state":"work_in_progress"}' where key='queue';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(r->>'state'='work_in_progress' and jsonb_array_length(r->'created_tasks')=0,'18 active lease wins over new source');
 update business_dedupe_cases set value='{"state":"planner_gap"}' where key='queue';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=1,'19 deferred merchant stock change is not lost');

 update business_dedupe_cases set value=value||'{"publication_verified":true,"next_evidence":"qualified_session"}' where key='fm';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=1 and (r->'created_tasks'->>0) like 'bizplan:funnel-truth:source-v1:%','20 verified source selects bounded funnel audit');
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=0,'21 funnel audits also deduplicate');
 perform pg_temp.dedupe_assert(r->>'paid_calls'='0' and r->>'new_spend_usd'='0','22 zero spend report preserved');
 perform pg_temp.dedupe_assert(not has_function_privilege('anon','public.plan_dufynd_autonomous_business_work_v1()','EXECUTE') and not has_function_privilege('authenticated','public.read_dufynd_business_source_v1(jsonb)','EXECUTE'),'23 private ACL preserved');
 perform pg_temp.dedupe_assert((select bool_and(not prosecdef) from pg_proc where oid in ('public.plan_dufynd_autonomous_business_work_v1()'::regprocedure,'public.read_dufynd_business_source_v1(jsonb)'::regprocedure)),'24 invoker rights preserved');

 -- Partial/unverified evidence is representable but must never grant publish
 -- permission or crash the entire planner on an optional JSON scalar.
 update public.dufynd_content_workflows set evidence='{"publication_observation":null}' where asset_id='dedupe-fixture-asset';
 update public.dufynd_master_status set value=jsonb_set(value,'{posts}','[null,"incomplete"]') where key='jarvis.thin_v1.first_money_schedule_observation';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=1,'25 partial proof and platform values remain inspectable');
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=0,'26 identical partial evidence does not loop');
 update business_dedupe_cases set value=jsonb_set(value,'{recent_signals}','[{"event_id":"second","occurred_at":"2026-10-02T09:00:00Z"},{"event_id":"first","occurred_at":"2026-10-02T09:00:00Z"}]') where key='fm';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 update business_dedupe_cases set value=jsonb_set(value,'{recent_signals}','[{"event_id":"first","occurred_at":"2026-10-02T09:00:00Z"},{"event_id":"second","occurred_at":"2026-10-02T09:00:00Z"}]') where key='fm';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=0,'27 equal-time event ordering is canonical');
 update public.dufynd_master_status set value=jsonb_set(value,'{posts}','["incomplete",null]') where key='jarvis.thin_v1.first_money_schedule_observation';
 r:=public.plan_dufynd_autonomous_business_work_v1();
 perform pg_temp.dedupe_assert(jsonb_array_length(r->'created_tasks')=0,'28 platform ordering is canonical even without IDs');
end $test$;

create function pg_temp.reject_dedupe_checkpoint() returns trigger language plpgsql as $$
begin
 if new.key='jarvis.business_source_dedupe_v1' then raise exception 'fixture checkpoint unavailable'; end if;
 return new;
end $$;
create trigger fixture_checkpoint_failure before insert or update on public.dufynd_master_status
 for each row execute function pg_temp.reject_dedupe_checkpoint();
do $test$
declare before_count bigint; saved jsonb;
begin
 select count(*) into before_count from public.dufynd_autonomy_tasks;
 select value into saved from public.dufynd_master_status where key='jarvis.business_source_dedupe_v1';
 update business_dedupe_cases set value=jsonb_set(value,'{purchase_evidence,price_eur}','73.9') where key='fm';
 begin
  perform public.plan_dufynd_autonomous_business_work_v1();
  raise exception 'fixture did not reject checkpoint';
 exception when raise_exception then
  if sqlerrm<>'fixture checkpoint unavailable' then raise; end if;
 end;
 perform pg_temp.dedupe_assert((select count(*)=before_count from public.dufynd_autonomy_tasks),'29 checkpoint failure rolls back inserted audit');
 perform pg_temp.dedupe_assert((select value=saved from public.dufynd_master_status where key='jarvis.business_source_dedupe_v1'),'30 checkpoint failure preserves previous source');
end $test$;
drop trigger fixture_checkpoint_failure on public.dufynd_master_status;
select pg_temp.dedupe_assert(jsonb_array_length(public.plan_dufynd_autonomous_business_work_v1()->'created_tasks')=1,'31 recovery processes pending genuine change once');
select label from business_dedupe_results order by label;
rollback;
