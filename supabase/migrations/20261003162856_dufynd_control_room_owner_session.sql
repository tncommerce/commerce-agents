-- A private, narrowly privileged boolean read of the caller's own auth session.
-- No user/session rows or secrets are exposed. No Jarvis grants change.
create schema if not exists dufynd_owner_private;
revoke all on schema dufynd_owner_private from public, anon, authenticated, service_role;
grant usage on schema dufynd_owner_private to authenticated;

create function dufynd_owner_private.session_alive(p_session_id uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null
    and coalesce(auth.jwt()->>'session_id', '') = p_session_id::text
    and exists (
      select 1 from auth.sessions s join auth.users u on u.id=s.user_id
      where s.id=p_session_id and s.user_id=auth.uid()
        and (s.not_after is null or s.not_after > now())
        and u.deleted_at is null and coalesce(u.is_anonymous,false)=false
        and u.email_confirmed_at is not null
        and (u.banned_until is null or u.banned_until <= now())
    );
$$;
revoke all on function dufynd_owner_private.session_alive(uuid) from public,anon,authenticated,service_role;
grant execute on function dufynd_owner_private.session_alive(uuid) to authenticated;

create function public.dufynd_dashboard_owner_session(p_session_id uuid)
returns boolean language sql stable security invoker set search_path = '' as $$
  select dufynd_owner_private.session_alive(p_session_id);
$$;
revoke all on function public.dufynd_dashboard_owner_session(uuid) from public,anon,authenticated,service_role;
grant execute on function public.dufynd_dashboard_owner_session(uuid) to authenticated;
