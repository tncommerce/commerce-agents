-- Private Observer acceptance gate.
-- A successful OIDC read may be durably captured before observer activation.
-- The session is short-lived, provenance-bound, service-role-only, and can
-- activate Render/Gmail only after all four captures plus idempotent Gmail ack.

create table public.dufynd_broker_acceptance_sessions (
  run_id bigint primary key,
  source_sha text not null check (source_sha ~ '^[a-f0-9]{40}$'),
  run_attempt integer not null check (run_attempt between 1 and 9999),
  status text not null check (status in ('capturing','captured','activated','failed')),
  captured_observers jsonb not null default '[]'::jsonb
    check (jsonb_typeof(captured_observers)='array'),
  ack_summary jsonb,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  finalized_at timestamptz
);

alter table public.dufynd_broker_acceptance_sessions enable row level security;
revoke all on public.dufynd_broker_acceptance_sessions from public,anon,authenticated;
grant select,insert,update,delete on public.dufynd_broker_acceptance_sessions to service_role;

create function public.begin_dufynd_broker_acceptance(p_source jsonb)
returns jsonb
language plpgsql
security invoker
set search_path=public
as $$
declare
  r bigint;
  a integer;
  s public.dufynd_broker_acceptance_sessions;
  healthy_count integer;
begin
  if jsonb_typeof(p_source) is distinct from 'object'
     or not (p_source ?& array[
       'version','repository','repository_id','repository_owner_id','ref',
       'workflow_ref','event_name','sha','run_id','run_attempt'
     ])
     or p_source - array[
       'version','repository','repository_id','repository_owner_id','ref',
       'workflow_ref','event_name','sha','run_id','run_attempt'
     ] <> '{}'::jsonb
     or p_source->>'version' is distinct from '1'
     or p_source->>'repository' is distinct from 'tncommerce/commerce-agents'
     or p_source->>'repository_id' is distinct from '1367576041'
     or p_source->>'repository_owner_id' is distinct from '324597697'
     or p_source->>'ref' is distinct from 'refs/heads/scentai-mvp'
     or p_source->>'workflow_ref' is distinct from
       'tncommerce/commerce-agents/.github/workflows/dufynd-private-observer.yml@refs/heads/scentai-mvp'
     or p_source->>'event_name' is distinct from 'workflow_dispatch'
     or coalesce(p_source->>'sha','') !~ '^[a-f0-9]{40}$'
     or coalesce(p_source->>'run_id','') !~ '^[0-9]{1,20}$'
     or coalesce(p_source->>'run_attempt','') !~ '^[0-9]{1,4}$'
  then
    raise exception 'invalid private observer acceptance provenance';
  end if;

  r := (p_source->>'run_id')::bigint;
  a := (p_source->>'run_attempt')::integer;
  perform pg_advisory_xact_lock(hashtext('dufynd-private-observer-acceptance'));

  select * into s
  from public.dufynd_broker_acceptance_sessions
  where run_id=r
  for update;

  if found then
    if s.source_sha is distinct from p_source->>'sha'
       or s.run_attempt is distinct from a then
      raise exception 'private observer acceptance provenance collision';
    end if;
    if s.status='activated' then
      return jsonb_build_object('accepted',true,'run_id',r,'state','activated','reused',true);
    end if;
    if s.expires_at <= now() then
      update public.dufynd_broker_acceptance_sessions
      set status='failed'
      where run_id=r;
      raise exception 'private observer acceptance expired';
    end if;
    return jsonb_build_object('accepted',true,'run_id',r,'state',s.status,'reused',true);
  end if;

  if exists (
    select 1 from public.dufynd_observer_credentials
    where provider in ('render','gmail') and activation_enabled
  ) then
    raise exception 'private observer already activated';
  end if;

  select count(*) into healthy_count
  from public.dufynd_observer_credentials c
  where c.provider in ('render','gmail')
    and (public.get_dufynd_credential_health(c.provider)->>'status') in ('healthy','expiring')
    and c.last_health_check >= now()-interval '5 minutes';

  if healthy_count <> 2 then
    raise exception 'private observer credential health not fresh';
  end if;

  insert into public.dufynd_broker_acceptance_sessions(
    run_id,source_sha,run_attempt,status,expires_at
  ) values (
    r,p_source->>'sha',a,'capturing',now()+interval '15 minutes'
  );

  return jsonb_build_object('accepted',true,'run_id',r,'state','capturing','reused',false);
end
$$;

create function public.capture_dufynd_broker_acceptance_observation(
  p_run_id bigint,
  p_credential_id text,
  p_observer_id text,
  p_evidence jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path=public
as $$
declare
  s public.dufynd_broker_acceptance_sessions;
  c public.dufynd_observer_credentials;
  o public.dufynd_external_observers;
  health jsonb;
  raw jsonb;
  x jsonb;
  messages jsonb := '[]'::jsonb;
  deployments jsonb := '[]'::jsonb;
  result jsonb;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-private-observer-acceptance'));

  select * into s
  from public.dufynd_broker_acceptance_sessions
  where run_id=p_run_id
  for update;

  if s.run_id is null
     or s.status not in ('capturing','captured')
     or s.expires_at <= now() then
    raise exception 'private observer acceptance session unavailable';
  end if;

  select * into c
  from public.dufynd_observer_credentials
  where credential_id=p_credential_id;

  select * into o
  from public.dufynd_external_observers
  where observer_id=p_observer_id;

  health := public.get_dufynd_credential_health(c.provider);

  if c.credential_id is null
     or o.observer_id is null
     or c.provider is distinct from o.source_type
     or not c.allowed_resources ? o.source_id
     or c.activation_enabled
     or health->>'status' not in ('healthy','expiring')
     or c.last_health_check is null
     or c.last_health_check < now()-interval '5 minutes'
     or not o.enabled then
    return jsonb_build_object('accepted',false,'reason','blocked_configuration');
  end if;

  if p_evidence is null or octet_length(p_evidence::text)>65536 then
    raise exception 'invalid bounded broker evidence';
  end if;

  if c.provider='render' then
    if jsonb_typeof(p_evidence) is distinct from 'array'
       or jsonb_array_length(p_evidence)>20 then
      raise exception 'invalid deployment evidence';
    end if;
    for x in select value from jsonb_array_elements(p_evidence) loop
      if jsonb_typeof(x) is distinct from 'object'
         or x-array['deployment_id','service_id','commit_sha','status','timestamps']<>'{}'::jsonb
         or x->>'service_id' is distinct from o.source_id
         or coalesce(x->>'deployment_id','') !~ '^dep-[a-z0-9]+$'
         or coalesce(x->>'commit_sha','') !~ '^[a-f0-9]{40}$'
         or coalesce(x->>'status','') not in (
           'live','created','queued','build_in_progress','update_in_progress',
           'pre_deploy_in_progress','build_failed','update_failed',
           'pre_deploy_failed','canceled','deactivated'
         ) then
        raise exception 'broker resource/shape mismatch';
      end if;
      deployments := deployments || jsonb_build_array(
        jsonb_build_object(
          'id',x->>'deployment_id',
          'status',x->>'status',
          'commit',jsonb_build_object('id',x->>'commit_sha')
        )
      );
    end loop;
    raw := deployments;
  else
    if jsonb_typeof(p_evidence) is distinct from 'object'
       or p_evidence-array['thread_id','history_id','messages']<>'{}'::jsonb
       or p_evidence->>'thread_id' is distinct from o.source_id
       or coalesce(p_evidence->>'history_id','') !~ '^[0-9]{1,30}$'
       or jsonb_typeof(p_evidence->'messages') is distinct from 'array'
       or jsonb_array_length(p_evidence->'messages')>100 then
      raise exception 'invalid thread evidence';
    end if;

    for x in select value from jsonb_array_elements(p_evidence->'messages') loop
      if jsonb_typeof(x) is distinct from 'object'
         or x-array['message_id','thread_id','internal_date','sender','delivery_failure']<>'{}'::jsonb
         or x->>'thread_id' is distinct from o.source_id
         or coalesce(x->>'message_id','') !~ '^[a-f0-9]{1,32}$'
         or coalesce(x->>'internal_date','') !~ '^[0-9]{1,16}$'
         or jsonb_typeof(x->'delivery_failure') is distinct from 'boolean'
         or length(coalesce(x->>'sender',''))>320
         or (
           coalesce(x->>'sender','')<>''
           and x->>'sender' !~ '^[a-z0-9.!#$%&''*+/=?^_{|}~-]+@[a-z0-9.-]+$'
         ) then
        raise exception 'foreign/invalid message rejected';
      end if;
      messages := messages || jsonb_build_array(
        jsonb_build_object(
          'id',x->>'message_id',
          'threadId',o.source_id,
          'internalDate',x->>'internal_date',
          'payload',jsonb_build_object(
            'headers',jsonb_build_array(
              jsonb_build_object('name','From','value',x->>'sender'),
              jsonb_build_object(
                'name','Content-Type',
                'value',case when (x->>'delivery_failure')::boolean
                  then 'delivery-status' else '' end
              )
            )
          )
        )
      );
    end loop;
    raw := jsonb_build_object(
      'id',o.source_id,
      'historyId',p_evidence->>'history_id',
      'messages',messages
    );
  end if;

  result := public.capture_dufynd_observation(p_observer_id,raw);
  if not coalesce((result->>'accepted')::boolean,false) then
    return result;
  end if;

  update public.dufynd_broker_acceptance_sessions
  set captured_observers = case
        when captured_observers ? p_observer_id then captured_observers
        else captured_observers || jsonb_build_array(p_observer_id)
      end
  where run_id=p_run_id;

  select * into s
  from public.dufynd_broker_acceptance_sessions
  where run_id=p_run_id
  for update;

  if s.captured_observers ?& array[
    'render:srv-dakpfrnf3r2c73dr3f20',
    'gmail:1a0f385ed98c6af8',
    'gmail:1a0f69c169fb928f',
    'gmail:1a0f6a90772a743d'
  ] then
    update public.dufynd_broker_acceptance_sessions
    set status='captured'
    where run_id=p_run_id;
  end if;

  return result || jsonb_build_object('acceptance_run_id',p_run_id);
end
$$;

create function public.finalize_dufynd_broker_acceptance(
  p_source jsonb,
  p_ack_summary jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path=public
as $$
declare
  r bigint;
  a integer;
  s public.dufynd_broker_acceptance_sessions;
  acked integer;
  dupes integer;
  rechecks integer;
  healthy_count integer;
begin
  if jsonb_typeof(p_source) is distinct from 'object'
     or coalesce(p_source->>'sha','') !~ '^[a-f0-9]{40}$'
     or coalesce(p_source->>'run_id','') !~ '^[0-9]{1,20}$'
     or coalesce(p_source->>'run_attempt','') !~ '^[0-9]{1,4}$'
     or p_source->>'repository' is distinct from 'tncommerce/commerce-agents'
     or p_source->>'repository_id' is distinct from '1367576041'
     or p_source->>'repository_owner_id' is distinct from '324597697'
     or p_source->>'ref' is distinct from 'refs/heads/scentai-mvp'
     or p_source->>'workflow_ref' is distinct from
       'tncommerce/commerce-agents/.github/workflows/dufynd-private-observer.yml@refs/heads/scentai-mvp'
     or p_source->>'event_name' is distinct from 'workflow_dispatch' then
    raise exception 'invalid private observer acceptance provenance';
  end if;

  if jsonb_typeof(p_ack_summary) is distinct from 'object'
     or not (p_ack_summary ?& array[
       'acknowledged','duplicate_first_pass','idempotent_rechecks'
     ])
     or p_ack_summary - array[
       'acknowledged','duplicate_first_pass','idempotent_rechecks'
     ] <> '{}'::jsonb then
    raise exception 'invalid private observer ack summary';
  end if;

  begin
    acked := (p_ack_summary->>'acknowledged')::integer;
    dupes := (p_ack_summary->>'duplicate_first_pass')::integer;
    rechecks := (p_ack_summary->>'idempotent_rechecks')::integer;
  exception when others then
    raise exception 'invalid private observer ack summary';
  end;

  if acked < 0 or dupes < 0 or acked+dupes <> 3 or rechecks <> 3 then
    raise exception 'private observer ack proof incomplete';
  end if;

  r := (p_source->>'run_id')::bigint;
  a := (p_source->>'run_attempt')::integer;
  perform pg_advisory_xact_lock(hashtext('dufynd-private-observer-acceptance'));

  select * into s
  from public.dufynd_broker_acceptance_sessions
  where run_id=r
  for update;

  if s.run_id is null
     or s.source_sha is distinct from p_source->>'sha'
     or s.run_attempt is distinct from a then
    raise exception 'private observer acceptance provenance mismatch';
  end if;

  if s.status='activated' then
    return jsonb_build_object(
      'accepted',true,'activated',2,'activation_changed',false,'run_id',r
    );
  end if;

  if s.status is distinct from 'captured' or s.expires_at <= now() then
    raise exception 'private observer acceptance not captured';
  end if;

  select count(*) into healthy_count
  from public.dufynd_observer_credentials c
  where c.provider in ('render','gmail')
    and not c.activation_enabled
    and (public.get_dufynd_credential_health(c.provider)->>'status') in ('healthy','expiring')
    and c.last_health_check >= now()-interval '10 minutes';

  if healthy_count <> 2 then
    raise exception 'private observer credential health not fresh';
  end if;

  update public.dufynd_observer_credentials
  set activation_enabled=true
  where provider in ('render','gmail');

  update public.dufynd_broker_acceptance_sessions
  set status='activated',
      ack_summary=p_ack_summary,
      finalized_at=now()
  where run_id=r;

  return jsonb_build_object(
    'accepted',true,'activated',2,'activation_changed',true,'run_id',r
  );
end
$$;

revoke all on function public.begin_dufynd_broker_acceptance(jsonb)
  from public,anon,authenticated;
revoke all on function public.capture_dufynd_broker_acceptance_observation(bigint,text,text,jsonb)
  from public,anon,authenticated;
revoke all on function public.finalize_dufynd_broker_acceptance(jsonb,jsonb)
  from public,anon,authenticated;

grant execute on function public.begin_dufynd_broker_acceptance(jsonb) to service_role;
grant execute on function public.capture_dufynd_broker_acceptance_observation(bigint,text,text,jsonb)
  to service_role;
grant execute on function public.finalize_dufynd_broker_acceptance(jsonb,jsonb) to service_role;
