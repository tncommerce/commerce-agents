-- Preserve the existing unique asset content_id index. A release groups distinct
-- platform content IDs through revision-bound metadata.release_content_id.
create or replace function public.register_dufynd_release_v1(p_release_id text,p_content_id text,p_kind text,p_assets jsonb)
returns jsonb language plpgsql security invoker set search_path=public as $$
<<fn>>
declare expected text[]; actual text[]; row record; prior public.dufynd_content_releases;
begin
 expected:=case p_kind when 'short' then array['instagram','tiktok','youtube'] when 'photo' then array['instagram','tiktok'] end;
 select array_agg(key order by key) into actual from jsonb_each_text(p_assets);
 if expected is null or actual is distinct from expected then raise exception 'all_expected_platforms_required'; end if;
 -- A repeated registration cannot replace an already reserved/approved asset.
 insert into public.dufynd_content_releases(release_id,content_id,kind) values(p_release_id,p_content_id,p_kind) on conflict do nothing;
 select * into prior from public.dufynd_content_releases where release_id=p_release_id for update;
 if not found or prior.content_id<>p_content_id or prior.kind<>p_kind then raise exception 'release_identity_conflict'; end if;
 for row in select key,value from jsonb_each_text(p_assets) loop
  if not exists(select 1 from public.dufynd_content_assets where id=row.value and platform=row.key and coalesce(metadata->>'release_content_id',content_id)=p_content_id
   and (p_kind<>'short' or coalesce(metadata->'publish_contract_v2'->>'media_kind','')=case row.key when 'instagram' then 'reel' else 'video' end)
   and (p_kind<>'photo' or coalesce(metadata->'publish_contract_v2'->>'media_kind','') in ('image','carousel'))) then raise exception 'asset_platform_content_or_format_mismatch'; end if;
  insert into public.dufynd_release_platforms(release_id,platform,asset_id,blocker) values(p_release_id,row.key,row.value,'preflight_required') on conflict do nothing;
  if not exists(select 1 from public.dufynd_release_platforms where release_id=p_release_id and platform=row.key and asset_id=row.value) then raise exception 'release_asset_replacement_forbidden'; end if;
 end loop;
 return jsonb_build_object('registered',true,'publishing_authorized',false);
end $$;

