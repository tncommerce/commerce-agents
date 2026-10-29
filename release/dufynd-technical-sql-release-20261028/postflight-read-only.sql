-- Read-only postconditions; no planner, poller, broker, task or business-action call.
begin read only;
set local statement_timeout='15s';
do $postflight_guard$
declare r record;
begin
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.plan_dufynd_free_work_v1()');
 if r.definition_md5 is null or r.definition_md5 not in ('048fa0a0c4f114e641fd97463848dc5c')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 'v' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.plan_dufynd_free_work_v1()';
 end if;
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.poll_dufynd_observers()');
 if r.definition_md5 is null or r.definition_md5 not in ('fdbb921ba914178935e81b2d2e3bde8e')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 'v' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.poll_dufynd_observers()';
 end if;
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.read_dufynd_safe_work_exhaustion_v1()');
 if r.definition_md5 is null or r.definition_md5 not in ('df57cc1746168a917c2d0a6bfe14bc07')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 's' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.read_dufynd_safe_work_exhaustion_v1()';
 end if;
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.read_dufynd_technical_work_blockers_v1()');
 if r.definition_md5 is null or r.definition_md5 not in ('0f9e888aa4d1f853d8a0fc0e9c84cb9b')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 's' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.read_dufynd_technical_work_blockers_v1()';
 end if;
end;
$postflight_guard$;
select p.oid::regprocedure::text as function,
 md5(pg_get_functiondef(p.oid)) as definition_md5,md5(p.prosrc) as source_md5,
 pg_get_userbyid(p.proowner) as owner,p.proacl::text as acl,
 p.prosecdef as security_definer,p.provolatile as volatility,p.proconfig as config,
 has_function_privilege('anon',p.oid,'EXECUTE') as anon_execute,
 has_function_privilege('authenticated',p.oid,'EXECUTE') as authenticated_execute,
 has_function_privilege('service_role',p.oid,'EXECUTE') as service_execute
from pg_proc p join pg_namespace n on n.oid=p.pronamespace
where n.nspname='public' and p.proname in (
 'poll_dufynd_observers','read_dufynd_technical_work_blockers_v1',
 'read_dufynd_safe_work_exhaustion_v1','plan_dufynd_free_work_v1')
order by p.proname;
select now() as observed_at,
 public.read_dufynd_technical_work_blockers_v1() as technical_work,
 public.read_dufynd_safe_work_exhaustion_v1() as exhaustion;

-- Observe the normal cron result. Do not run the planner/poller to create evidence.
select key,last_verified_at,value->>'state' as state,value->>'reason' as reason,
 value->>'operational_state' as operational_state,
 value->>'technical_repair_executed' as technical_repair_executed,
 value->>'new_spend_usd' as new_spend_usd
from public.dufynd_master_status where key='jarvis.planner_v1';
select source_type,enabled,health_status,count(*) as observers,
 min(last_success_at) as oldest_success,max(last_success_at) as newest_success
from public.dufynd_external_observers
where source_type in ('render','gmail','github_branch')
group by source_type,enabled,health_status order by source_type,enabled,health_status;
select status,count(*) as tasks from public.dufynd_autonomy_tasks group by status order by status;
select count(*) filter(where active) as active_cron_jobs from cron.job;
select status,count(*) as runs,min(start_time) as first_start,max(start_time) as latest_start
from cron.job_run_details where start_time>=now()-interval '20 minutes'
group by status order by status;

-- Security catalog deltas: the two technical migrations must not add a public RPC.
select count(*) as public_definer_rpcs_callable
from pg_proc p join pg_namespace n on n.oid=p.pronamespace
where n.nspname='public' and p.prosecdef
and (has_function_privilege('anon',p.oid,'EXECUTE')
 or has_function_privilege('authenticated',p.oid,'EXECUTE'));
select count(*) as policyless_rls_tables
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public' and c.relkind in ('r','p') and c.relrowsecurity
and not exists(select 1 from pg_policy p where p.polrelid=c.oid);
select p.oid::regprocedure::text as procedure,md5(pg_get_functiondef(p.oid)) as definition_md5,
 p.prokind,p.proacl::text as acl,p.proconfig as config
from pg_proc p join pg_namespace n on n.oid=p.pronamespace
where n.nspname='public' and p.proname in ('dufynd_ns_v1_cycle','dufynd_ns_v1_pilot_abort')
order by p.proname;
commit;
