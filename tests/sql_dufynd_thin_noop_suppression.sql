-- Isolation: execute only on temporary migrated-schema Postgres; always rollback.
begin;
do $test$
declare before_count bigint; after_count bigint; answer jsonb;
begin
  if (select count(*) from public.dufynd_master_status where key='jarvis.thin_v1.config')<>1 then raise exception 'missing config'; end if;
  update public.dufynd_master_status set value=jsonb_set(value,'{periodic_health_tasks}','false'::jsonb,true) where key='jarvis.thin_v1.config';
  if position('periodic_health_tasks' in pg_get_functiondef('public.run_dufynd_thin_v1()'::regprocedure))=0 then raise exception 'missing no-op guard';end if;
  select count(*) into before_count from public.dufynd_autonomy_tasks where task_id like 'thin-health:%';
  answer:=public.run_dufynd_thin_v1();
  select count(*) into after_count from public.dufynd_autonomy_tasks where task_id like 'thin-health:%';
  if after_count<>before_count then raise exception 'generated synthetic health work despite flag=false';end if;
  if coalesce((answer->>'paid_calls')::int,0)<>0 then raise exception 'unexpected provider spend';end if;
  -- Operational rollback is a config flag, not a cron/revision change.
  update public.dufynd_master_status set value=jsonb_set(value,'{periodic_health_tasks}','true'::jsonb,true) where key='jarvis.thin_v1.config';
  if (select value->>'periodic_health_tasks' from public.dufynd_master_status where key='jarvis.thin_v1.config')<>'true' then raise exception 'rollback switch broken';end if;
  if has_function_privilege('anon','public.run_dufynd_thin_v1()','execute') or has_function_privilege('authenticated','public.run_dufynd_thin_v1()','execute') then raise exception 'public execution leaked';end if;
end $test$;
rollback;
