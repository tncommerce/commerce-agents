-- Operational suspension only; this file is not an automatic migration.
-- An owner must first disable the v2 workflow/bridge and both scope rows.
-- Their normal UPDATE trigger immediately blocks only marked v2 observers.
-- Existing v1 scope, captures, credentials and all audit evidence are retained.
-- Use a single explicit transaction so a guard failure changes nothing.
begin;

select pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));

do $rollback$
declare
 definition text; body text;
 added constant text:=E'\n perform public.refresh_dufynd_render_service_health_v2();';
begin
 if exists(select 1 from public.dufynd_render_observer_scopes_v2 where enabled) then
  raise exception 'render v2 rollback requires every service scope disabled';
 end if;
 if exists(select 1 from public.dufynd_external_observers
  where enabled and source_type='render'
   and source_id in ('srv-dakpfrnf3r2c73dr3f20','srv-dakpiajl550s73cp4lvg')
   and last_snapshot->>'scope_id'='render_services_v2'
   and health_status is distinct from 'blocked_configuration') then
  raise exception 'render v2 rollback requires marked observers reconciled';
 end if;
 select pg_get_functiondef(oid),prosrc into definition,body
 from pg_proc where oid='public.poll_dufynd_observers()'::regprocedure;
 if length(body)-length(replace(body,added,''))<>length(added)
  or md5(replace(body,added,'')) is distinct from 'c07e9e3bd5233031014209b8526f1348' then
  raise exception 'render v2 rollback poller source mismatch';
 end if;
 execute replace(definition,added,'');
end
$rollback$;

revoke execute on function public.capture_dufynd_render_service_read_v2(jsonb,jsonb)
 from public,anon,authenticated,service_role;

-- Leave owner-only configuration, its proof fields, receipts, events and the
-- disabled-scope reconciler in place. Reopening v2 is a separate reviewed
-- release with a current runtime/transport proof and explicit service grant.
commit;
