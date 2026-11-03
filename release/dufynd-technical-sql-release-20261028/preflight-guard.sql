-- Read-only guards against the fresh live catalog fingerprints supplied on 2026-10-28.
do $release_guard$
declare r record;
begin
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.plan_dufynd_free_work_v1()');
 if r.definition_md5 is null or r.definition_md5 not in ('0fb393ff9dcd50376772556c73a6d07d')
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
 if r.definition_md5 is null or r.definition_md5 not in ('b16099ccc4633cafb48dcb81044738ad')
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
 if r.definition_md5 is null or r.definition_md5 not in ('9b85321f0afb551ceb44700ab458eff7')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 's' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.read_dufynd_safe_work_exhaustion_v1()';
 end if;
 if to_regprocedure('public.read_dufynd_technical_work_blockers_v1()') is not null then
  raise exception 'DUFYND release requires absent helper: public.read_dufynd_technical_work_blockers_v1()';
 end if;
end;
$release_guard$;
