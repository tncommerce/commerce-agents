-- Staged Render v2 permissions. These are additional explicit service grants;
-- the old API-only credential, v1 endpoint and activation remain unchanged.
-- Merely applying this migration cannot register, enable or refresh an observer.
create table public.dufynd_render_observer_scopes_v2 (
 service_id text primary key check(service_id in
  ('srv-dakpfrnf3r2c73dr3f20','srv-dakpiajl550s73cp4lvg')),
 scope_id text not null default 'render_services_v2' check(scope_id='render_services_v2'),
 credential_id text not null default 'render_deploy_broker'
  references public.dufynd_observer_credentials(credential_id)
  check(credential_id='render_deploy_broker'),
 enabled boolean not null default false,
 runtime_source_sha text check(runtime_source_sha ~ '^[a-f0-9]{40}$'),
 runtime_image_digest text check(runtime_image_digest ~ '^sha256:[a-f0-9]{64}$'),
 verified_at timestamptz check(verified_at is null or isfinite(verified_at)),
 check(not enabled or
  (runtime_source_sha is not null and runtime_image_digest is not null and verified_at is not null))
);
alter table public.dufynd_render_observer_scopes_v2 enable row level security;
revoke all on public.dufynd_render_observer_scopes_v2 from public,anon,authenticated,service_role;
grant select on public.dufynd_render_observer_scopes_v2 to service_role;
create policy dufynd_render_scope_v2_service_read
 on public.dufynd_render_observer_scopes_v2 for select to service_role using (true);

-- The owner must record independently verified existing-runtime evidence and
-- enable each scope explicitly. The workflow cannot write these grants.
insert into public.dufynd_render_observer_scopes_v2(service_id)
values ('srv-dakpfrnf3r2c73dr3f20'),('srv-dakpiajl550s73cp4lvg');

create function public.lock_dufynd_render_scope_change_v2()
returns trigger language plpgsql security invoker set search_path=pg_catalog,public
as $function$
begin
 -- TRUNCATE takes an AccessExclusive table lock before statement triggers.
 -- Waiting for our advisory lock there would invert the capture lock order.
 -- Owner-maintenance uses serialized UPDATE/DELETE for these two fixed rows.
 if TG_OP='TRUNCATE' then
  raise exception 'render v2 scopes cannot be truncated; disable or delete explicit service rows';
 end if;
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 return null;
end
$function$;
revoke all on function public.lock_dufynd_render_scope_change_v2() from public,anon,authenticated,service_role;
grant execute on function public.lock_dufynd_render_scope_change_v2() to postgres;
create trigger dufynd_render_scope_change_v2
 before insert or update or delete or truncate on public.dufynd_render_observer_scopes_v2
 for each statement execute function public.lock_dufynd_render_scope_change_v2();

create function public.dufynd_render_source_valid_v2(p_source jsonb)
returns boolean language plpgsql immutable security invoker set search_path=pg_catalog,public
as $function$
begin
 if jsonb_typeof(p_source) is distinct from 'object' then return false; end if;
 return coalesce(
  octet_length(p_source::text)<=4096
  and p_source ?& array['version','repository','repository_id','repository_owner_id',
   'ref','workflow_ref','event_name','sha','run_id','run_attempt']
  and p_source-array['version','repository','repository_id','repository_owner_id',
   'ref','workflow_ref','event_name','sha','run_id','run_attempt']='{}'::jsonb
  and p_source->'version'='1'::jsonb and p_source->>'version'='1'
  and not exists(select 1 from jsonb_each(p_source) x
   where x.key<>'version' and jsonb_typeof(x.value)<>'string')
  and p_source->>'repository'='tncommerce/commerce-agents'
  and p_source->>'repository_id'='1367576041'
  and p_source->>'repository_owner_id'='324597697'
  and p_source->>'ref'='refs/heads/scentai-mvp'
  and p_source->>'workflow_ref'=
   'tncommerce/commerce-agents/.github/workflows/dufynd-private-observer.yml@refs/heads/scentai-mvp'
  and p_source->>'event_name' in ('workflow_dispatch','schedule')
  and p_source->>'sha' ~ '^[a-f0-9]{40}$'
  and p_source->>'run_id' ~ '^[1-9][0-9]{0,19}$'
  and p_source->>'run_attempt' ~ '^[1-9][0-9]{0,3}$',false);
end
$function$;
revoke all on function public.dufynd_render_source_valid_v2(jsonb) from public,anon,authenticated;
grant execute on function public.dufynd_render_source_valid_v2(jsonb) to service_role,postgres;

create function public.capture_dufynd_render_service_read_v2(p_source jsonb,p_observation jsonb)
returns jsonb language plpgsql security invoker set search_path=pg_catalog,public
as $function$
declare
 s public.dufynd_render_observer_scopes_v2;
 o public.dufynd_external_observers;
 c public.dufynd_observer_credentials;
 prior public.dufynd_master_status;
 service_key text; observer_key text; receipt_key text;
 observation_keys constant text[]:=array['version','scope_id','service_id','observed_at','deployments'];
 receipt_keys constant text[]:=array['version','mode','scope_id','source','service_id','observer_id',
  'observed_at','captured_at','evidence_sha256','accepted','reused','render_captures',
  'gmail_captures','acks','activation_changed','business_success','full_chain_complete'];
 stamp_pattern constant text:='^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$';
 x jsonb; v jsonb; k text; raw jsonb:='[]'; first_deploy jsonb;
 observed_at timestamptz; consumed_at timestamptz; parsed_at timestamptz;
 prior_observed_at timestamptz; prior_captured_at timestamptz;
 fingerprint text; capture jsonb; receipt jsonb;
begin
 if not public.dufynd_render_source_valid_v2(p_source) then
  return jsonb_build_object('accepted',false,'reason','invalid_render_source');
 end if;
 if jsonb_typeof(p_observation) is distinct from 'object' then
  return jsonb_build_object('accepted',false,'reason','invalid_render_observation');
 end if;
 if octet_length(p_observation::text)>65536
  or not (p_observation ?& observation_keys)
  or p_observation-observation_keys<>'{}'::jsonb
  or p_observation->'version' is distinct from '2'::jsonb
  or p_observation->>'version' is distinct from '2'
  or p_observation->'scope_id' is distinct from '"render_services_v2"'::jsonb
  or jsonb_typeof(p_observation->'service_id') is distinct from 'string'
  or p_observation->>'service_id' not in ('srv-dakpfrnf3r2c73dr3f20','srv-dakpiajl550s73cp4lvg')
  or jsonb_typeof(p_observation->'observed_at') is distinct from 'string'
  or length(p_observation->>'observed_at')>40
  or p_observation->>'observed_at' !~ stamp_pattern
  or jsonb_typeof(p_observation->'deployments') is distinct from 'array' then
  return jsonb_build_object('accepted',false,'reason','invalid_render_observation');
 end if;
 service_key:=p_observation->>'service_id';
 observer_key:='render:'||service_key;
 receipt_key:='ops.private_observer.render_capture_v2.'||service_key;
 if jsonb_array_length(p_observation->'deployments') not between 1 and 20 then
  return jsonb_build_object('accepted',false,'reason','invalid_render_observation');
 end if;
 begin
  observed_at:=(p_observation->>'observed_at')::timestamptz;
 exception when invalid_datetime_format or datetime_field_overflow or invalid_time_zone_displacement_value then
  return jsonb_build_object('accepted',false,'reason','invalid_render_observation');
 end;
 if not isfinite(observed_at) then
  return jsonb_build_object('accepted',false,'reason','invalid_render_observation');
 end if;
 for x in select value from jsonb_array_elements(p_observation->'deployments') loop
  if jsonb_typeof(x) is distinct from 'object' then
   return jsonb_build_object('accepted',false,'reason','invalid_render_observation');
  end if;
  if not (x ?& array['deployment_id','service_id','commit_sha','status','timestamps'])
   or x-array['deployment_id','service_id','commit_sha','status','timestamps']<>'{}'::jsonb
   or jsonb_typeof(x->'deployment_id') is distinct from 'string'
   or x->>'deployment_id' !~ '^dep-[a-z0-9]{1,100}$'
   or x->'service_id' is distinct from to_jsonb(service_key)
   or jsonb_typeof(x->'commit_sha') is distinct from 'string'
   or x->>'commit_sha' !~ '^[a-f0-9]{40}$'
   or jsonb_typeof(x->'status') is distinct from 'string'
   or x->>'status' not in ('live','created','queued','build_in_progress','update_in_progress',
    'pre_deploy_in_progress','build_failed','update_failed','pre_deploy_failed','canceled','deactivated')
   or jsonb_typeof(x->'timestamps') is distinct from 'object' then
   return jsonb_build_object('accepted',false,'reason','invalid_render_observation');
  end if;
  if not (x->'timestamps' ?& array['createdAt','updatedAt','startedAt','finishedAt'])
   or (x->'timestamps')-array['createdAt','updatedAt','startedAt','finishedAt']<>'{}'::jsonb then
   return jsonb_build_object('accepted',false,'reason','invalid_render_observation');
  end if;
  for v in select value from jsonb_each(x->'timestamps') loop
   if v='null'::jsonb then continue; end if;
   if jsonb_typeof(v) is distinct from 'string' or length(v#>>'{}')>40
    or v#>>'{}' !~ stamp_pattern then
    return jsonb_build_object('accepted',false,'reason','invalid_render_observation');
   end if;
   begin
    parsed_at:=(v#>>'{}')::timestamptz;
   exception when invalid_datetime_format or datetime_field_overflow or invalid_time_zone_displacement_value then
    return jsonb_build_object('accepted',false,'reason','invalid_render_observation');
   end;
   if not isfinite(parsed_at) then
    return jsonb_build_object('accepted',false,'reason','invalid_render_observation');
   end if;
  end loop;
  raw:=raw||jsonb_build_array(jsonb_build_object('id',x->>'deployment_id',
   'status',x->>'status','commit',jsonb_build_object('id',x->>'commit_sha')));
 end loop;
 if (select count(distinct item.value->>'deployment_id')
  from jsonb_array_elements(p_observation->'deployments') item(value))
  <>jsonb_array_length(p_observation->'deployments') then
  return jsonb_build_object('accepted',false,'reason','invalid_render_observation');
 end if;

 -- Same lock order as v1. Scope writers take this lock in a statement trigger;
 -- their owner-only grant changes therefore serialize without giving the
 -- capture role UPDATE rights on the permission table.
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 select * into s from public.dufynd_render_observer_scopes_v2 where service_id=service_key;
 select * into o from public.dufynd_external_observers where observer_id=observer_key for update;
 select * into c from public.dufynd_observer_credentials where credential_id='render_deploy_broker' for update;
 select * into prior from public.dufynd_master_status where key=receipt_key for update;
 consumed_at:=clock_timestamp();
 if s.service_id is null or s.enabled is distinct from true
  or s.scope_id is distinct from 'render_services_v2'
  or s.credential_id is distinct from 'render_deploy_broker'
  or s.runtime_source_sha is null or s.runtime_source_sha !~ '^[a-f0-9]{40}$'
  or s.runtime_image_digest is null or s.runtime_image_digest !~ '^sha256:[a-f0-9]{64}$'
  or s.verified_at is null or not isfinite(s.verified_at) or s.verified_at>consumed_at then
  return jsonb_build_object('accepted',false,'reason','render_scope_unverified');
 end if;
 if o.observer_id is null or o.enabled is distinct from true
  or o.source_type is distinct from 'render' or o.source_id is distinct from service_key
  or c.credential_id is null or c.provider is distinct from 'render'
  or c.activation_enabled is distinct from true or c.status not in ('healthy','expiring')
  or c.revoked_at is not null
  or (c.expires_at is not null and (not isfinite(c.expires_at) or c.expires_at<=consumed_at))
  or c.allowed_resources is distinct from '["srv-dakpfrnf3r2c73dr3f20"]'::jsonb
  or c.allowed_operations is distinct from '["deployment.read"]'::jsonb then
  return jsonb_build_object('accepted',false,'reason','blocked_configuration');
 end if;
 fingerprint:=encode(sha256(convert_to(jsonb_build_object(
  'source',p_source,'observation',p_observation)::text,'UTF8')),'hex');
 if prior.key is not null then
  if jsonb_typeof(prior.value) is distinct from 'object' then
   return jsonb_build_object('accepted',false,'reason','render_receipt_invalid');
  end if;
  if not (prior.value ?& receipt_keys) or prior.value-receipt_keys<>'{}'::jsonb
   or prior.value->'version' is distinct from '2'::jsonb
   or prior.value->>'version' is distinct from '2'
   or prior.value->'mode' is distinct from '"render_services_v2"'::jsonb
   or prior.value->'scope_id' is distinct from '"render_services_v2"'::jsonb
   or prior.value->'service_id' is distinct from to_jsonb(service_key)
   or prior.value->'observer_id' is distinct from to_jsonb(observer_key)
   or not public.dufynd_render_source_valid_v2(prior.value->'source')
   or prior.value->'accepted' is distinct from 'true'::jsonb
   or prior.value->'reused' is distinct from 'false'::jsonb
   or prior.value->'render_captures' is distinct from '1'::jsonb
   or prior.value->>'render_captures' is distinct from '1'
   or prior.value->'gmail_captures' is distinct from '0'::jsonb
   or prior.value->>'gmail_captures' is distinct from '0'
   or prior.value->'acks' is distinct from '0'::jsonb
   or prior.value->>'acks' is distinct from '0'
   or prior.value->'activation_changed' is distinct from 'false'::jsonb
   or prior.value->'business_success' is distinct from 'false'::jsonb
   or prior.value->'full_chain_complete' is distinct from 'false'::jsonb
   or jsonb_typeof(prior.value->'evidence_sha256') is distinct from 'string'
   or prior.value->>'evidence_sha256' !~ '^[a-f0-9]{64}$' then
   return jsonb_build_object('accepted',false,'reason','render_receipt_invalid');
  end if;
  foreach k in array array['observed_at','captured_at'] loop
   if jsonb_typeof(prior.value->k) is distinct from 'string' or length(prior.value->>k)>40
    or prior.value->>k !~ stamp_pattern then
    return jsonb_build_object('accepted',false,'reason','render_receipt_invalid');
   end if;
   begin
    parsed_at:=(prior.value->>k)::timestamptz;
   exception when invalid_datetime_format or datetime_field_overflow or invalid_time_zone_displacement_value then
    return jsonb_build_object('accepted',false,'reason','render_receipt_invalid');
   end;
   if not isfinite(parsed_at) then
    return jsonb_build_object('accepted',false,'reason','render_receipt_invalid');
   end if;
   if k='observed_at' then prior_observed_at:=parsed_at; else prior_captured_at:=parsed_at; end if;
  end loop;
  if prior_observed_at>prior_captured_at or prior_captured_at>consumed_at then
   return jsonb_build_object('accepted',false,'reason','render_receipt_invalid');
  end if;
  if prior.value->'source'->>'run_id'=p_source->>'run_id' then
   if prior.value->'source'->>'run_attempt'=p_source->>'run_attempt' then
    if prior.value->'source' is distinct from p_source
     or prior.value->>'evidence_sha256' is distinct from fingerprint then
     return jsonb_build_object('accepted',false,'reason','render_receipt_conflict');
    end if;
    -- A replay acknowledges committed evidence, without changing its age,
    -- metadata, event count, scope, observer state or stored receipt.
    return prior.value||jsonb_build_object('reused',true,'render_captures',0);
   end if;
   if (p_source->>'run_attempt')::integer<(prior.value->'source'->>'run_attempt')::integer then
    return jsonb_build_object('accepted',false,'reason','superseded_render_observation');
   end if;
   if p_source-'run_attempt' is distinct from (prior.value->'source')-'run_attempt' then
    return jsonb_build_object('accepted',false,'reason','render_receipt_conflict');
   end if;
  end if;
  if (p_source->>'run_id')::numeric<(prior.value->'source'->>'run_id')::numeric then
   return jsonb_build_object('accepted',false,'reason','superseded_render_observation');
  end if;
 end if;
 if observed_at>consumed_at or observed_at<consumed_at-interval '5 minutes'
  or observed_at<s.verified_at then
  return jsonb_build_object('accepted',false,'reason','stale_render_observation');
 end if;
 if (prior_observed_at is not null and observed_at<=prior_observed_at)
  or (o.last_success_at is not null and (not isfinite(o.last_success_at) or observed_at<=o.last_success_at)) then
  return jsonb_build_object('accepted',false,'reason','superseded_render_observation');
 end if;
 capture:=public.capture_dufynd_observation(observer_key,raw);
 if capture->'accepted' is distinct from 'true'::jsonb then
  raise exception 'render service capture rejected';
 end if;
 first_deploy:=p_observation->'deployments'->0;
 update public.dufynd_external_observers
 set last_success_at=observed_at,last_attempt_at=observed_at,
  next_retry_at=consumed_at+make_interval(secs=>interval_seconds),
  last_snapshot=jsonb_build_object('service_id',service_key,'scope_id','render_services_v2',
   'deployment_id',first_deploy->>'deployment_id','sha',first_deploy->>'commit_sha',
   'state',case when first_deploy->>'status'='live' then 'live'
    when first_deploy->>'status' in ('build_failed','update_failed','pre_deploy_failed','canceled') then 'failed'
    when first_deploy->>'status'='deactivated' then 'deactivated' else 'started' end)
 where observer_id=observer_key;
 receipt:=jsonb_build_object('version',2,'mode','render_services_v2','scope_id','render_services_v2',
  'source',p_source,'service_id',service_key,'observer_id',observer_key,'observed_at',observed_at,
  'captured_at',consumed_at,'evidence_sha256',fingerprint,'accepted',true,'reused',false,
  'render_captures',1,'gmail_captures',0,'acks',0,'activation_changed',false,
  'business_success',false,'full_chain_complete',false);
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values(receipt_key,'ops',receipt,100,consumed_at)
 on conflict(key) do update set value=excluded.value,last_verified_at=excluded.last_verified_at;
 return receipt;
end
$function$;
revoke all on function public.capture_dufynd_render_service_read_v2(jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.capture_dufynd_render_service_read_v2(jsonb,jsonb) to service_role,postgres;

-- Only a real v2 capture writes this marker. Revoking a new grant cannot block
-- an independently fresh v1 API capture whose snapshot has no v2 marker.
create function public.refresh_dufynd_render_service_health_v2()
returns jsonb language plpgsql security invoker set search_path=pg_catalog,public
as $function$
declare
 o public.dufynd_external_observers;
 s public.dufynd_render_observer_scopes_v2;
 c public.dufynd_observer_credentials;
 checked_at timestamptz; reason text; changed integer; blocked integer:=0;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 for o in select * from public.dufynd_external_observers
  where enabled and source_type='render'
   and source_id in ('srv-dakpfrnf3r2c73dr3f20','srv-dakpiajl550s73cp4lvg')
   and last_snapshot->>'scope_id'='render_services_v2'
  order by observer_id for update loop
  select * into s from public.dufynd_render_observer_scopes_v2 where service_id=o.source_id;
  select * into c from public.dufynd_observer_credentials where credential_id='render_deploy_broker' for update;
  checked_at:=clock_timestamp();
  reason:=null;
  if s.service_id is null or s.enabled is distinct from true
   or s.scope_id is distinct from 'render_services_v2'
   or s.credential_id is distinct from 'render_deploy_broker'
   or s.runtime_source_sha is null or s.runtime_source_sha !~ '^[a-f0-9]{40}$'
   or s.runtime_image_digest is null or s.runtime_image_digest !~ '^sha256:[a-f0-9]{64}$'
   or s.verified_at is null or not isfinite(s.verified_at) or s.verified_at>checked_at
   or o.last_success_at is null or o.last_success_at<s.verified_at
   or o.observer_id is distinct from 'render:'||o.source_id
   or o.last_snapshot->>'service_id' is distinct from o.source_id then
   reason:='render_service_scope_unverified';
  elsif c.credential_id is null or c.provider is distinct from 'render'
   or c.activation_enabled is distinct from true or c.status not in ('healthy','expiring')
   or c.revoked_at is not null
   or (c.expires_at is not null and (not isfinite(c.expires_at) or c.expires_at<=checked_at))
   or c.allowed_resources is distinct from '["srv-dakpfrnf3r2c73dr3f20"]'::jsonb
   or c.allowed_operations is distinct from '["deployment.read"]'::jsonb then
   reason:='render_credential_unavailable';
  end if;
  if reason is not null then
   update public.dufynd_external_observers
    set health_status='blocked_configuration',last_error=reason,request_id=null,request_started_at=null
    where observer_id=o.observer_id and
     (health_status is distinct from 'blocked_configuration' or last_error is distinct from reason
      or request_id is not null or request_started_at is not null);
   get diagnostics changed=row_count;
   blocked:=blocked+changed;
  end if;
 end loop;
 return jsonb_build_object('blocked',blocked,'activation_changed',false,'business_success',false);
end
$function$;
revoke all on function public.refresh_dufynd_render_service_health_v2() from public,anon,authenticated;
grant execute on function public.refresh_dufynd_render_service_health_v2() to service_role,postgres;

create function public.reconcile_dufynd_render_scope_change_v2()
returns trigger language plpgsql security invoker set search_path=pg_catalog,public
as $function$
begin
 perform public.refresh_dufynd_render_service_health_v2();
 return null;
end
$function$;
revoke all on function public.reconcile_dufynd_render_scope_change_v2() from public,anon,authenticated,service_role;
grant execute on function public.reconcile_dufynd_render_scope_change_v2() to postgres;
create trigger dufynd_render_scope_reconcile_v2
 after insert or update or delete on public.dufynd_render_observer_scopes_v2
 for each statement execute function public.reconcile_dufynd_render_scope_change_v2();

-- Preserve the exact existing poller, including its ACL, owner, search path and
-- independent GitHub/public-health hooks. Unexpected source changes stop here.
do $patch$
declare definition text; body_hash text;
 needle constant text:='perform pg_advisory_xact_lock(hashtext(''dufynd-supervisor-v2-claims''));';
begin
 select pg_get_functiondef(oid),md5(prosrc) into definition,body_hash
 from pg_proc where oid='public.poll_dufynd_observers()'::regprocedure;
 if body_hash is distinct from 'c07e9e3bd5233031014209b8526f1348'
  or length(definition)-length(replace(definition,needle,''))<>length(needle) then
  raise exception 'render v2 poller baseline mismatch';
 end if;
 execute replace(definition,needle,needle||E'\n perform public.refresh_dufynd_render_service_health_v2();');
end
$patch$;
