-- Independent Render monitoring uses the already activated API credential.
-- No new provider scope, observer, schedule, activation or acceptance session.
-- A single private receipt makes retries atomic without refreshing old evidence.
create or replace function public.capture_dufynd_render_observer_read_v1(
 p_source jsonb,p_health jsonb,p_evidence jsonb
) returns jsonb
language plpgsql security invoker set search_path=public as $function$
declare
 o public.dufynd_external_observers;
 c public.dufynd_observer_credentials;
 prior public.dufynd_master_status;
 receipt_key constant text := 'ops.private_observer.render_capture_v1';
 observer_key constant text := 'render:srv-dakpfrnf3r2c73dr3f20';
 source_keys constant text[] := array['version','repository','repository_id','repository_owner_id',
  'ref','workflow_ref','event_name','sha','run_id','run_attempt'];
 health_time_keys constant text[] := array['expires_at','refreshed_at','revoked_at',
  'last_health_check','rotation_due_at'];
 k text; provider text; h jsonb; x jsonb; v jsonb;
 parsed_at timestamptz; observed_at timestamptz; prior_observed_at timestamptz;
 consumed_at timestamptz; fingerprint text; projection jsonb; capture jsonb; receipt jsonb;
begin
 if jsonb_typeof(p_source) is distinct from 'object'
  or not (p_source ?& source_keys) or p_source-source_keys <> '{}'::jsonb
  or p_source->'version' is distinct from '1'::jsonb then
  return jsonb_build_object('accepted',false,'reason','invalid_render_source');
 end if;
 foreach k in array source_keys loop
  if k<>'version' and jsonb_typeof(p_source->k) is distinct from 'string' then
   return jsonb_build_object('accepted',false,'reason','invalid_render_source');
  end if;
 end loop;
 if p_source->>'repository' is distinct from 'tncommerce/commerce-agents'
  or p_source->>'repository_id' is distinct from '1367576041'
  or p_source->>'repository_owner_id' is distinct from '324597697'
  or p_source->>'ref' is distinct from 'refs/heads/scentai-mvp'
  or p_source->>'workflow_ref' is distinct from
   'tncommerce/commerce-agents/.github/workflows/dufynd-private-observer.yml@refs/heads/scentai-mvp'
  or p_source->>'event_name' not in ('workflow_dispatch','schedule')
  or p_source->>'sha' !~ '^[a-f0-9]{40}$'
  or p_source->>'run_id' !~ '^[1-9][0-9]{0,19}$'
  or p_source->>'run_attempt' !~ '^[1-9][0-9]{0,3}$' then
  return jsonb_build_object('accepted',false,'reason','invalid_render_source');
 end if;
 if jsonb_typeof(p_health) is distinct from 'object'
  or not (p_health ?& array['render','gmail'])
  or p_health-array['render','gmail'] <> '{}'::jsonb
  or p_evidence is null or octet_length(p_evidence::text)>65536
  or jsonb_typeof(p_evidence) is distinct from 'array' then
  raise exception 'invalid bounded render evidence';
 end if;
 if jsonb_array_length(p_evidence) not between 1 and 20 then
  raise exception 'invalid bounded render evidence';
 end if;
 -- Validate temporal types without accepting infinity, naive local dates or
 -- timezone parse errors. The existing projector validates the full metadata.
 foreach provider in array array['render','gmail'] loop
  h:=p_health->provider;
  if jsonb_typeof(h) is distinct from 'object' or not (h ?& health_time_keys) then
   raise exception 'invalid broker health timestamp';
  end if;
  foreach k in array health_time_keys loop
   v:=h->k;
   if v='null'::jsonb and k<>'last_health_check' then continue; end if;
   if jsonb_typeof(v) is distinct from 'string' or length(h->>k)>40
    or h->>k !~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$' then
    raise exception 'invalid broker health timestamp';
   end if;
   begin
    parsed_at:=(h->>k)::timestamptz;
   exception when invalid_datetime_format or datetime_field_overflow or invalid_time_zone_displacement_value then
    raise exception 'invalid broker health timestamp';
   end;
   if not isfinite(parsed_at) then raise exception 'invalid broker health timestamp'; end if;
   if provider='render' and k='last_health_check' then observed_at:=parsed_at; end if;
  end loop;
 end loop;
 for x in select value from jsonb_array_elements(p_evidence) loop
  if jsonb_typeof(x) is distinct from 'object'
   or not (x ?& array['deployment_id','service_id','commit_sha','status','timestamps'])
   or x-array['deployment_id','service_id','commit_sha','status','timestamps'] <> '{}'::jsonb
   or jsonb_typeof(x->'deployment_id') is distinct from 'string'
   or x->>'deployment_id' !~ '^dep-[a-z0-9]+$'
   or jsonb_typeof(x->'service_id') is distinct from 'string'
   or x->>'service_id' is distinct from 'srv-dakpfrnf3r2c73dr3f20'
   or jsonb_typeof(x->'commit_sha') is distinct from 'string'
   or x->>'commit_sha' !~ '^[a-f0-9]{40}$'
   or jsonb_typeof(x->'status') is distinct from 'string'
   or x->>'status' not in ('live','created','queued','build_in_progress','update_in_progress',
    'pre_deploy_in_progress','build_failed','update_failed','pre_deploy_failed','canceled','deactivated')
   or jsonb_typeof(x->'timestamps') is distinct from 'object'
   or not (x->'timestamps' ?& array['createdAt','updatedAt','startedAt','finishedAt'])
   or (x->'timestamps')-array['createdAt','updatedAt','startedAt','finishedAt'] <> '{}'::jsonb then
   raise exception 'invalid bounded render evidence';
  end if;
  for v in select value from jsonb_each(x->'timestamps') loop
   if v='null'::jsonb then continue; end if;
   if jsonb_typeof(v) is distinct from 'string' or length(v#>>'{}')>40
    or v#>>'{}' !~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$' then
    raise exception 'invalid deployment timestamp';
   end if;
   begin
    parsed_at:=(v#>>'{}')::timestamptz;
   exception when invalid_datetime_format or datetime_field_overflow or invalid_time_zone_displacement_value then
    raise exception 'invalid deployment timestamp';
   end;
   if not isfinite(parsed_at) then raise exception 'invalid deployment timestamp'; end if;
  end loop;
 end loop;

 -- Same outer lock and observer-row order as the existing capture. Credential
 -- locks follow the projector's Render-before-Gmail order, all before the clock.
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 select * into o from public.dufynd_external_observers where observer_id=observer_key for update;
 select * into c from public.dufynd_observer_credentials where credential_id='render_deploy_broker' for update;
 perform 1 from public.dufynd_observer_credentials where credential_id='gmail_known_threads' for update;
 select * into prior from public.dufynd_master_status where key=receipt_key for update;
 consumed_at:=clock_timestamp();
 if o.observer_id is null or o.enabled is distinct from true
  or o.source_type is distinct from 'render' or o.source_id is distinct from 'srv-dakpfrnf3r2c73dr3f20'
  or c.credential_id is null or c.provider is distinct from 'render'
  or c.activation_enabled is distinct from true
  or c.allowed_resources is distinct from '["srv-dakpfrnf3r2c73dr3f20"]'::jsonb
  or c.allowed_operations is distinct from '["deployment.read"]'::jsonb then
  return jsonb_build_object('accepted',false,'reason','blocked_configuration');
 end if;
 fingerprint:=encode(sha256(convert_to(jsonb_build_object(
  'source',p_source,'health',p_health,'evidence',p_evidence)::text,'UTF8')),'hex');
 if prior.key is not null then
  if jsonb_typeof(prior.value) is distinct from 'object'
   or jsonb_typeof(prior.value->'source') is distinct from 'object'
   or jsonb_typeof(prior.value->'observed_at') is distinct from 'string'
   or coalesce(prior.value->>'evidence_sha256','') !~ '^[a-f0-9]{64}$'
   or coalesce(prior.value->'source'->>'run_id','') !~ '^[1-9][0-9]{0,19}$'
   or coalesce(prior.value->'source'->>'run_attempt','') !~ '^[1-9][0-9]{0,3}$' then
   return jsonb_build_object('accepted',false,'reason','render_receipt_invalid');
  end if;
  begin
   prior_observed_at:=(prior.value->>'observed_at')::timestamptz;
  exception when invalid_datetime_format or datetime_field_overflow or invalid_time_zone_displacement_value then
   return jsonb_build_object('accepted',false,'reason','render_receipt_invalid');
  end;
  if not isfinite(prior_observed_at) or prior_observed_at>consumed_at then
   return jsonb_build_object('accepted',false,'reason','render_receipt_invalid');
  end if;
  if prior.value->'source'->>'run_id'=p_source->>'run_id' then
   if prior.value->'source'->>'run_attempt'=p_source->>'run_attempt' then
    if prior.value->'source' is distinct from p_source
     or prior.value->>'evidence_sha256' is distinct from fingerprint then
     return jsonb_build_object('accepted',false,'reason','render_receipt_conflict');
    end if;
    -- A committed read may be acknowledged again even after its freshness
    -- window, but never mutates health, observation, cursor or receipt times.
    return jsonb_build_object('accepted',true,'reused',true,'render_captures',0,
     'gmail_captures',0,'acks',0,'activation_changed',false,'full_chain_complete',false,
     'business_success',false,'observed_at',prior_observed_at);
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
  or (p_health->'gmail'->>'last_health_check')::timestamptz>consumed_at
  or (p_health->'gmail'->>'last_health_check')::timestamptz<consumed_at-interval '5 minutes' then
  return jsonb_build_object('accepted',false,'reason','stale_render_observation');
 end if;
 if (prior_observed_at is not null and observed_at<=prior_observed_at)
  or (o.last_success_at is not null and (not isfinite(o.last_success_at) or observed_at<=o.last_success_at))
  or (c.last_health_check is not null and (not isfinite(c.last_health_check) or observed_at<c.last_health_check)) then
  return jsonb_build_object('accepted',false,'reason','superseded_render_observation');
 end if;
 -- These existing gates still check exact immutable provider metadata, current
 -- health and activation. A rejection rolls back the preceding projection.
 projection:=public.project_dufynd_broker_health(p_health);
 if projection->'projected' is distinct from '2'::jsonb
  or projection->'activation_changed' is distinct from 'false'::jsonb then
  raise exception 'broker health projection mismatch';
 end if;
 capture:=public.capture_dufynd_broker_observation('render_deploy_broker',observer_key,p_evidence);
 if capture->'accepted' is distinct from 'true'::jsonb then
  raise exception 'render capture rejected';
 end if;
 update public.dufynd_external_observers
 set last_success_at=observed_at,last_attempt_at=observed_at,
  next_retry_at=consumed_at+make_interval(secs=>interval_seconds)
 where observer_id=observer_key;
 receipt:=jsonb_build_object('version',1,'mode','render','source',p_source,
  'observer_id',observer_key,'observed_at',observed_at,'captured_at',consumed_at,
  'evidence_sha256',fingerprint,'accepted',true,'reused',false,'render_captures',1,
  'gmail_captures',0,'acks',0,'activation_changed',false,'full_chain_complete',false,
  'business_success',false);
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values(receipt_key,'ops',receipt,100,consumed_at)
 on conflict(key) do update set value=excluded.value,last_verified_at=excluded.last_verified_at;
 return receipt;
end
$function$;

revoke all on function public.capture_dufynd_render_observer_read_v1(jsonb,jsonb,jsonb)
 from public,anon,authenticated;
grant execute on function public.capture_dufynd_render_observer_read_v1(jsonb,jsonb,jsonb)
 to service_role;
