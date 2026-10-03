-- Fail-closed activation gate for the private Render/Gmail observer broker.
-- Activation remains false until a fresh provenance-bound health preflight exists.

create or replace function public.guard_dufynd_private_observer_activation()
returns trigger
language plpgsql
security invoker
set search_path=public
as $$
begin
  if new.activation_enabled
     and not old.activation_enabled
     and coalesce(current_setting('dufynd.private_observer_activation', true),'') <> 'allowed' then
    raise exception 'private observer activation requires guarded preflight';
  end if;
  return new;
end
$$;

drop trigger if exists dufynd_private_observer_activation_guard
on public.dufynd_observer_credentials;
create trigger dufynd_private_observer_activation_guard
before update of activation_enabled
on public.dufynd_observer_credentials
for each row
execute function public.guard_dufynd_private_observer_activation();

create or replace function public.record_dufynd_private_observer_preflight(p_source jsonb)
returns jsonb
language plpgsql
security invoker
set search_path=public
as $$
declare
  render_health jsonb;
  gmail_health jsonb;
  verified_at timestamptz := now();
  result jsonb;
  required_source_keys text[] := array[
    'version','repository','repository_id','repository_owner_id','ref',
    'workflow_ref','event_name','sha','run_id','run_attempt'
  ];
begin
  if jsonb_typeof(p_source) is distinct from 'object'
     or not (p_source ?& required_source_keys)
     or p_source - required_source_keys <> '{}'::jsonb
     or p_source->>'version' is distinct from '1'
     or p_source->>'repository' is distinct from 'tncommerce/commerce-agents'
     or p_source->>'repository_id' is distinct from '1367576041'
     or p_source->>'repository_owner_id' is distinct from '324597697'
     or p_source->>'ref' is distinct from 'refs/heads/scentai-mvp'
     or p_source->>'workflow_ref' is distinct from
        'tncommerce/commerce-agents/.github/workflows/dufynd-private-observer.yml@refs/heads/scentai-mvp'
     or p_source->>'event_name' not in ('workflow_dispatch','schedule')
     or coalesce(p_source->>'sha','') !~ '^[a-f0-9]{40}$'
     or coalesce(p_source->>'run_id','') !~ '^[0-9]{1,20}$'
     or coalesce(p_source->>'run_attempt','') !~ '^[0-9]{1,4}$' then
    raise exception 'invalid private observer source provenance';
  end if;

  render_health := public.get_dufynd_credential_health('render');
  gmail_health := public.get_dufynd_credential_health('gmail');

  if render_health->>'status' not in ('healthy','expiring')
     or gmail_health->>'status' not in ('healthy','expiring')
     or coalesce((render_health->>'activation_enabled')::boolean,false)
     or coalesce((gmail_health->>'activation_enabled')::boolean,false)
     or render_health->>'last_health_check' is null
     or gmail_health->>'last_health_check' is null
     or (render_health->>'last_health_check')::timestamptz < verified_at-interval '5 minutes'
     or (gmail_health->>'last_health_check')::timestamptz < verified_at-interval '5 minutes'
     or (render_health->>'last_health_check')::timestamptz > verified_at+interval '1 minute'
     or (gmail_health->>'last_health_check')::timestamptz > verified_at+interval '1 minute' then
    raise exception 'private observer preflight health not acceptable';
  end if;

  result := jsonb_build_object(
    'status','preflight_accepted',
    'source',p_source,
    'verified_at',verified_at,
    'render_status',render_health->>'status',
    'gmail_status',gmail_health->>'status',
    'activation_enabled',false
  );

  insert into public.dufynd_master_status(
    key,category,value,priority,last_verified_at,updated_at
  )
  values(
    'jarvis.private_observer.preflight','jarvis',result,100,verified_at,verified_at
  )
  on conflict(key) do update
  set category=excluded.category,
      value=excluded.value,
      priority=excluded.priority,
      last_verified_at=excluded.last_verified_at,
      updated_at=excluded.updated_at;

  return result;
end
$$;

create or replace function public.set_dufynd_private_observer_activation(
  p_run_id text,
  p_sha text,
  p_enabled boolean
)
returns jsonb
language plpgsql
security invoker
set search_path=public
as $$
declare
  preflight public.dufynd_master_status;
  render_health jsonb;
  gmail_health jsonb;
  source jsonb;
  changed integer;
  registered integer;
  activated_at timestamptz := now();
  result jsonb;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-private-observer-activation'));

  if p_enabled is not true then
    update public.dufynd_observer_credentials
    set activation_enabled=false
    where credential_id in ('render_deploy_broker','gmail_known_threads');

    update public.dufynd_external_observers
    set health_status='blocked_configuration',
        last_error='broker_activation_required',
        request_id=null,
        request_started_at=null
    where source_type in ('render','gmail');

    result := jsonb_build_object(
      'status','disabled',
      'activation_enabled',false,
      'disabled_at',activated_at
    );

    insert into public.dufynd_master_status(
      key,category,value,priority,last_verified_at,updated_at
    )
    values(
      'jarvis.private_observer.activation','jarvis',result,100,activated_at,activated_at
    )
    on conflict(key) do update
    set category=excluded.category,
        value=excluded.value,
        priority=excluded.priority,
        last_verified_at=excluded.last_verified_at,
        updated_at=excluded.updated_at;

    return result;
  end if;

  if coalesce(p_run_id,'') !~ '^[0-9]{1,20}$'
     or coalesce(p_sha,'') !~ '^[a-f0-9]{40}$' then
    raise exception 'invalid private observer activation provenance';
  end if;

  select *
  into preflight
  from public.dufynd_master_status
  where key='jarvis.private_observer.preflight'
  for update;

  if preflight.key is null
     or preflight.last_verified_at is null
     or preflight.last_verified_at < activated_at-interval '10 minutes'
     or preflight.last_verified_at > activated_at+interval '1 minute'
     or preflight.value->>'status' is distinct from 'preflight_accepted'
     or coalesce((preflight.value->>'activation_enabled')::boolean,true)
     or preflight.value->'source'->>'run_id' is distinct from p_run_id
     or preflight.value->'source'->>'sha' is distinct from p_sha then
    raise exception 'private observer activation preflight missing or stale';
  end if;

  source := preflight.value->'source';
  render_health := public.get_dufynd_credential_health('render');
  gmail_health := public.get_dufynd_credential_health('gmail');

  if render_health->>'status' not in ('healthy','expiring')
     or gmail_health->>'status' not in ('healthy','expiring')
     or render_health->>'last_health_check' is null
     or gmail_health->>'last_health_check' is null
     or (render_health->>'last_health_check')::timestamptz < activated_at-interval '5 minutes'
     or (gmail_health->>'last_health_check')::timestamptz < activated_at-interval '5 minutes'
     or (render_health->>'last_health_check')::timestamptz > activated_at+interval '1 minute'
     or (gmail_health->>'last_health_check')::timestamptz > activated_at+interval '1 minute' then
    raise exception 'private observer activation health not acceptable';
  end if;

  select count(*)
  into registered
  from public.dufynd_external_observers
  where enabled
    and (
      (observer_id='render:srv-dakpfrnf3r2c73dr3f20'
       and source_type='render'
       and source_id='srv-dakpfrnf3r2c73dr3f20')
      or
      (observer_id='gmail:1a0f385ed98c6af8'
       and source_type='gmail'
       and source_id='1a0f385ed98c6af8')
      or
      (observer_id='gmail:1a0f69c169fb928f'
       and source_type='gmail'
       and source_id='1a0f69c169fb928f')
      or
      (observer_id='gmail:1a0f6a90772a743d'
       and source_type='gmail'
       and source_id='1a0f6a90772a743d')
    );

  if registered <> 4 then
    raise exception 'private observer registered source set mismatch';
  end if;

  perform set_config('dufynd.private_observer_activation','allowed',true);
  update public.dufynd_observer_credentials
  set activation_enabled=true
  where credential_id in ('render_deploy_broker','gmail_known_threads');
  get diagnostics changed = row_count;

  if changed <> 2 then
    raise exception 'private observer credential set mismatch';
  end if;

  result := jsonb_build_object(
    'status','activated',
    'activation_enabled',true,
    'source',source,
    'activated_at',activated_at,
    'credentials_activated',changed,
    'registered_observers',registered
  );

  insert into public.dufynd_master_status(
    key,category,value,priority,last_verified_at,updated_at
  )
  values(
    'jarvis.private_observer.activation','jarvis',result,100,activated_at,activated_at
  )
  on conflict(key) do update
  set category=excluded.category,
      value=excluded.value,
      priority=excluded.priority,
      last_verified_at=excluded.last_verified_at,
      updated_at=excluded.updated_at;

  return result;
end
$$;

revoke all on function public.guard_dufynd_private_observer_activation(),
  public.record_dufynd_private_observer_preflight(jsonb),
  public.set_dufynd_private_observer_activation(text,text,boolean)
from public,anon,authenticated;

grant execute on function public.record_dufynd_private_observer_preflight(jsonb),
  public.set_dufynd_private_observer_activation(text,text,boolean)
to service_role;
