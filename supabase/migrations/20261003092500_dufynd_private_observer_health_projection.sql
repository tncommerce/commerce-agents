-- Project only bounded, non-secret broker health into the existing credential plane.
-- This function never enables activation and never accepts provider credentials.
create or replace function public.project_dufynd_broker_health(p_health jsonb)
returns jsonb
language plpgsql
security invoker
set search_path=public
as $$
declare
  p text;
  h jsonb;
  c public.dufynd_observer_credentials;
  checked_at timestamptz;
  projected jsonb;
  immutable_keys text[] := array[
    'credential_id','provider','account_alias','allowed_operations','allowed_resources',
    'oauth_scopes','secret_reference','status','expires_at','refreshed_at','revoked_at',
    'last_health_check','health_reason','rotation_due_at'
  ];
begin
  if jsonb_typeof(p_health) is distinct from 'object'
     or not (p_health ?& array['gmail','render'])
     or p_health - array['gmail','render'] <> '{}'::jsonb then
    raise exception 'invalid bounded broker health';
  end if;

  foreach p in array array['render','gmail'] loop
    h := p_health->p;
    if jsonb_typeof(h) is distinct from 'object'
       or not (h ?& immutable_keys)
       or h - immutable_keys <> '{}'::jsonb then
      raise exception 'invalid bounded broker health';
    end if;

    select * into c
    from public.dufynd_observer_credentials
    where provider=p
    for update;

    if c.credential_id is null
       or h->>'credential_id' is distinct from c.credential_id
       or h->>'provider' is distinct from c.provider
       or h->>'account_alias' is distinct from c.account_alias
       or h->'allowed_operations' is distinct from c.allowed_operations
       or h->'allowed_resources' is distinct from c.allowed_resources
       or h->'oauth_scopes' is distinct from c.oauth_scopes
       or h->>'secret_reference' is distinct from c.secret_reference then
      raise exception 'broker health contract mismatch';
    end if;

    if h->>'status' not in (
         'missing_configuration','healthy','expiring','expired','revoked',
         'refresh_failed','scope_mismatch','account_mismatch'
       )
       or h->>'health_reason' not in (
         'missing_configuration','healthy','expiring','expired','revoked',
         'refresh_failed','scope_mismatch','account_mismatch','rate_limited',
         'provider_outage','rotation_secret_missing','refresh_race','invalid_grant',
         'invalid_response','broker_activation_required'
       )
       or jsonb_typeof(h->'last_health_check') is distinct from 'string'
       or jsonb_typeof(h->'expires_at') not in ('string','null')
       or jsonb_typeof(h->'refreshed_at') not in ('string','null')
       or jsonb_typeof(h->'revoked_at') not in ('string','null')
       or jsonb_typeof(h->'rotation_due_at') not in ('string','null') then
      raise exception 'invalid broker health state';
    end if;

    begin
      checked_at := (h->>'last_health_check')::timestamptz;
      perform nullif(h->>'expires_at','')::timestamptz;
      perform nullif(h->>'refreshed_at','')::timestamptz;
      perform nullif(h->>'revoked_at','')::timestamptz;
      perform nullif(h->>'rotation_due_at','')::timestamptz;
    exception when others then
      raise exception 'invalid broker health timestamp';
    end;

    if checked_at < now()-interval '5 minutes'
       or checked_at > now()+interval '1 minute' then
      raise exception 'stale broker health';
    end if;

    if p='gmail'
       and h->>'status' in ('healthy','expiring','expired')
       and h->>'expires_at' is null then
      raise exception 'invalid broker health state';
    end if;

    update public.dufynd_observer_credentials
    set status=h->>'status',
        health_reason=h->>'health_reason',
        expires_at=nullif(h->>'expires_at','')::timestamptz,
        refreshed_at=nullif(h->>'refreshed_at','')::timestamptz,
        revoked_at=nullif(h->>'revoked_at','')::timestamptz,
        last_health_check=checked_at,
        rotation_due_at=nullif(h->>'rotation_due_at','')::timestamptz
    where credential_id=c.credential_id;

    projected := public.get_dufynd_credential_health(p);
    if projected->>'status' is distinct from h->>'status' then
      raise exception 'broker health state mismatch';
    end if;
  end loop;

  return jsonb_build_object(
    'projected',2,
    'activation_changed',false,
    'render',public.get_dufynd_credential_health('render'),
    'gmail',public.get_dufynd_credential_health('gmail')
  );
end
$$;

revoke all on function public.project_dufynd_broker_health(jsonb)
from public,anon,authenticated;
grant execute on function public.project_dufynd_broker_health(jsonb)
to service_role;
