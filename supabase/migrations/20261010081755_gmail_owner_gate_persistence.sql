-- An invalid grant does not heal after one hour. Supersede it only with newer broker health.
-- Non-secret health repair and one durable, actionable alert per incident.
-- No email, OAuth, activation, provider or credential material is changed here.
create or replace function public.reconcile_dufynd_gmail_health_v1()
returns jsonb language plpgsql security invoker set search_path=public as $$
declare
 h jsonb; prior jsonb; failure jsonb; incident jsonb; report jsonb;
 successes integer; issue text; action text; episode text; reauth boolean := false;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-gmail-health-v1'));
 update public.dufynd_observer_credentials
 set status='expired',health_reason='expired'
 where provider='gmail' and status in ('healthy','expiring') and expires_at<=now();
 h := public.get_dufynd_credential_health('gmail');
 select value into prior from public.dufynd_master_status where key='ops.gmail_observer.alert_v1';
 select value into failure from public.dufynd_master_status
 where key='ops.private_observer.last_failure'
 and last_verified_at>=coalesce(public.dufynd_parse_timestamp(h->>'refreshed_at'),'-infinity'::timestamptz);
 select value into incident from public.dufynd_master_status
 where key='ops.gmail_observer_expiration_incident_20261010';
 select count(*) into successes from public.dufynd_external_observers
 where source_type='gmail' and enabled and health_status='healthy'
 and observer_id in ('gmail:1a0f385ed98c6af8','gmail:1a0f69c169fb928f','gmail:1a0f6a90772a743d')
 and last_success_at>now()-interval '20 minutes'
 and last_success_at>=coalesce((h->>'refreshed_at')::timestamptz,'infinity');
 if h->>'status' not in ('healthy','expiring') then
  issue := 'credential_'||coalesce(h->>'status','missing_configuration');
 elsif not coalesce((h->>'activation_enabled')::boolean,false) then
  issue := 'broker_activation_required';
 elsif successes<>3 then issue := 'gmail_observer_stale';
 else issue := 'recovered'; end if;
 -- Keep a proven owner gate until a newer credential refresh supersedes it.
 -- An expired access token alone does NOT prove re-consent is needed.
 reauth := coalesce((h->>'owner_reauthorization_required')::boolean,false)
  or (coalesce(failure->>'stage','') like 'gmail_%'
      and coalesce(failure->>'reason','') in ('invalid_grant','revoked','missing_configuration'));
 if issue='recovered' then
  action := 'No action: three fresh broker reads and credential health verified.';
  reauth := false;
 elsif reauth then
  action := 'Owner: use the existing private broker owner client to POST /owner/oauth/gmail/start, open its one-use Google URL and consent once for gmail.metadata; rerun Private Observer Read. Never paste secrets or state/code URLs.';
 else
  action := 'Operator: verify Private Observer Read and Watchdog are enabled; dispatch the existing scentai-mvp read path once, inspect its sanitized failure receipt and require three fresh reads before recovery.';
 end if;
 episode := case when prior is not null and prior->>'state'<>'recovered'
  then prior->>'dedup_key' else 'gmail-observer:'||coalesce(h->>'expires_at','missing') end;
 report := jsonb_build_object('state',issue,'checked_at',now(),'credential',h,
  'fresh_successes',successes,'required_successes',3,'dedup_key',episode,
  'first_seen_at',case when prior->>'dedup_key'=episode then prior->'first_seen_at' else to_jsonb(now()) end,
  'action',action,'owner_action_required',reauth,'last_failure',failure,
  'prior_email_notified',coalesce((incident->'notification'->>'owner_alerted')::boolean,false),
  'email_sent',false,'new_spend_usd',0);
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values('ops.gmail_observer.alert_v1','ops',report,100,now())
 on conflict(key) do update set value=excluded.value,last_verified_at=excluded.last_verified_at;
 return report;
end $$;
revoke all on function public.reconcile_dufynd_gmail_health_v1() from public,anon,authenticated;
grant execute on function public.reconcile_dufynd_gmail_health_v1() to service_role,postgres;

