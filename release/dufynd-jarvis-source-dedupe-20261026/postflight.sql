-- Postflight for the exact reviewed migration. Catalog checks only: no planner invocation and no business-row writes.
do $dufynd_release_guard$
declare p pg_proc%rowtype;
begin
  if current_user <> 'postgres' then
    raise exception 'DUFYND release guard: execute as the verified postgres owner';
  end if;

  select * into p from pg_proc where oid=to_regprocedure('public.plan_dufynd_autonomous_business_work_v1()');
  if not found or md5(pg_get_functiondef(p.oid)) is distinct from '8668638435b216b4c0dd9fa535448669' then
    raise exception 'DUFYND release guard: unexpected function definition: public.plan_dufynd_autonomous_business_work_v1()';
  end if;
  if pg_get_userbyid(p.proowner)<>'postgres' or p.prosecdef or
     p.proconfig is distinct from array['search_path=public']::text[] or
     obj_description(p.oid,'pg_proc') is not null or
     (select array_agg(a::text order by a::text) from unnest(p.proacl) a)
       is distinct from array['postgres=X/postgres','service_role=X/postgres']::text[] then
    raise exception 'DUFYND release guard: unexpected owner, ACL, invoker mode, search path or comment: public.plan_dufynd_autonomous_business_work_v1()';
  end if;

  select * into p from pg_proc where oid=to_regprocedure('public.read_dufynd_business_source_v1(jsonb)');
  if not found or md5(pg_get_functiondef(p.oid)) is distinct from '6b8852a51087ba57bf2222481e651bc7' then
    raise exception 'DUFYND release guard: unexpected function definition: public.read_dufynd_business_source_v1(jsonb)';
  end if;
  if pg_get_userbyid(p.proowner)<>'postgres' or p.prosecdef or
     p.proconfig is distinct from array['search_path=public']::text[] or
     obj_description(p.oid,'pg_proc') is not null or
     (select array_agg(a::text order by a::text) from unnest(p.proacl) a)
       is distinct from array['postgres=X/postgres','service_role=X/postgres']::text[] then
    raise exception 'DUFYND release guard: unexpected owner, ACL, invoker mode, search path or comment: public.read_dufynd_business_source_v1(jsonb)';
  end if;
end;
$dufynd_release_guard$;
