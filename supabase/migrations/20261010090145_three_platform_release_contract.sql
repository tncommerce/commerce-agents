-- One durable release, three explicit platforms; no implicit GO or provider calls.
-- Enforce the audio contract in the existing production owner-review and workflow gates.
-- No publisher, public permissions, asset backfill or owner approval is created.
create or replace function public.dufynd_content_audio_v3_reason(m jsonb, platform text)
returns text language plpgsql stable security invoker set search_path=public as $$
<<fn>>
declare
 p jsonb:=m->'publish_contract_v2'; a jsonb:=p->'audio_contract';
 kind text:=lower(coalesce(m->>'content_kind',''));
 media text:=lower(coalesce(p->>'media_kind',''));
 mode text:=lower(coalesce(a->>'mode','')); delivery text:=lower(coalesce(a->>'delivery',''));
 k text; proof jsonb; width_px int; height_px int;
begin
 if platform not in ('instagram','tiktok','youtube') then return null; end if;
 if kind not in ('meme','editorial','education','product') then return 'social_content_kind_required'; end if;
 if jsonb_typeof(a) is distinct from 'object' then return 'audio_contract_required'; end if;
 if (platform='instagram' and media='reel') or (platform in ('tiktok','youtube') and media='video') then
  if coalesce(p->>'width_px','') !~ '^[0-9]{3,5}$' or coalesce(p->>'height_px','') !~ '^[0-9]{3,5}$' then return 'video_dimensions_invalid'; end if;
  width_px:=(p->>'width_px')::int; height_px:=(p->>'height_px')::int;
  if width_px<1080 or height_px<1920 or width_px*16<>height_px*9 then return 'video_requires_1080x1920_9_16'; end if;
  if p->'genuine_motion_verified' is distinct from 'true'::jsonb then return 'genuine_video_motion_not_verified'; end if;
 end if;
 for k in select unnest(array['duplicate_content','safe_zones','sharpness_compression','platform_caption','sound_timing']) loop
  proof:=m->'publication_checks_v3'->k;
  if proof->'passed' is distinct from 'true'::jsonb or length(trim(coalesce(proof->>'evidence_ref','')))=0
   or coalesce(m->>'asset_sha256','') !~ '^[a-f0-9]{64}$' or proof->>'asset_sha256' is distinct from m->>'asset_sha256' then return 'publication_check_missing_or_failed_'||k; end if;
 end loop;
 if mode='intentional_silence' then
  if kind='meme' then return 'silent_meme_forbidden'; end if;
  if kind not in ('editorial','education') then return 'silent_exception_content_kind_invalid'; end if;
  if jsonb_typeof(a->'owner_silence_exception_ref') is distinct from 'string'
    or length(trim(coalesce(a->>'owner_silence_exception_ref','')))=0
    or length(trim(coalesce(a->>'silence_editorial_reason','')))=0 then return 'intentional_silence_owner_exception_missing'; end if;
  return null;
 end if;
 for k in select unnest(array['commercial_rights_evidence_ref','audible_preview_evidence_ref']) loop
  if jsonb_typeof(a->k) is distinct from 'string' or length(trim(coalesce(a->>k,'')))=0 then return 'audio_'||k||'_required'; end if;
 end loop;
 if a->'audible_preview_verified' is distinct from 'true'::jsonb then return 'audio_playback_not_verified'; end if;
 if a->'commercial_music_rights_verified' is distinct from 'true'::jsonb then return 'audio_commercial_rights_not_verified'; end if;
 if jsonb_typeof(a->'audio_score') is distinct from 'number' then return 'audio_quality_below_owner_standard'; end if;
 if (a->>'audio_score')::numeric<9.5 or (a->>'audio_score')::numeric>10 then return 'audio_quality_below_owner_standard'; end if;
 if platform='instagram' and media in ('image','carousel','story') then
  if mode<>'instagram_native_music' or delivery not in ('instagram_native_app','metricool_notification') then return 'instagram_photo_audio_requires_native_handoff'; end if;
  if a->'native_track_selected_and_preheard' is distinct from 'true'::jsonb then return 'instagram_native_audio_not_preheard'; end if;
 elsif platform='instagram' and media='reel' and mode='metricool_reel_library' then
  if delivery<>'metricool_auto' then return 'instagram_reel_music_delivery_invalid'; end if;
  if a->'facebook_connection_verified' is distinct from 'true'::jsonb or a->'instagram_business_verified' is distinct from 'true'::jsonb
   or length(trim(coalesce(a->>'connection_evidence_ref','')))=0 then return 'instagram_reel_connection_unverified'; end if;
  if jsonb_typeof(a->'audio_id') is distinct from 'string' or length(trim(coalesce(a->>'audio_id','')))=0 then return 'instagram_reel_audio_id_required'; end if;
  if a->'native_track_selected_and_preheard' is distinct from 'true'::jsonb then return 'instagram_native_audio_not_preheard'; end if;
 elsif mode='embedded_video' and ((platform='instagram' and media='reel') or (platform in ('tiktok','youtube') and media='video')) then
  if delivery not in ('metricool_auto','instagram_native_app','tiktok_native_app','metricool_notification') then return 'embedded_audio_delivery_invalid'; end if;
  if coalesce(a->>'final_video_sha256','') !~ '^[a-f0-9]{64}$' or a->>'final_video_sha256' is distinct from m->>'asset_sha256' then return 'embedded_audio_video_digest_mismatch'; end if;
  if a->>'audio_codec' is distinct from 'aac' or length(trim(coalesce(a->>'audio_stream_evidence_ref','')))=0 then return 'embedded_audio_stream_unverified'; end if;
  if a->'full_playback_verified' is distinct from 'true'::jsonb or a->'timing_verified' is distinct from 'true'::jsonb or a->'loudness_verified' is distinct from 'true'::jsonb then return 'embedded_audio_full_playback_timing_loudness_required'; end if;
 elsif platform='instagram' and media='reel' and mode='instagram_native_music' then
  if delivery not in ('instagram_native_app','metricool_notification') or a->'native_track_selected_and_preheard' is distinct from 'true'::jsonb then return 'instagram_native_reel_requires_manual_handoff'; end if;
 elsif platform='tiktok' and media in ('image','carousel','video') and mode='tiktok_native_music' then
  if delivery not in ('tiktok_native_app','metricool_notification') or a->'native_track_selected_and_preheard' is distinct from 'true'::jsonb then return 'tiktok_requires_preheard_native_audio'; end if;
 else return 'platform_audio_mode_invalid'; end if;
 return null;
end $$;

revoke all on function public.dufynd_content_audio_v3_reason(jsonb,text) from public,anon,authenticated;
grant execute on function public.dufynd_content_audio_v3_reason(jsonb,text) to service_role;

create or replace function public.read_dufynd_publish_packet_v1(p_asset_id text) returns jsonb
language plpgsql stable security invoker set search_path=public as $$
<<fn>>
declare a public.dufynd_content_assets; w public.dufynd_content_workflows; d public.dufynd_human_decisions;
 fp text; reason text; c jsonb; p jsonb;
begin
 select * into a from public.dufynd_content_assets where id=p_asset_id;
 if not found then return jsonb_build_object('ready',false,'reason','asset_missing'); end if;
 select * into w from public.dufynd_content_workflows where asset_id=a.id;
 if not found or w.state is distinct from 'owner_approved' then
  return jsonb_build_object('ready',false,'reason','review_workflow_not_owner_approved'); end if;
 fp:=public.dufynd_content_revision(a.id);
 reason:=public.dufynd_content_workflow_qa_reason(a.id);
 if reason is not null then return jsonb_build_object('ready',false,'reason',reason); end if;
 c:=a.metadata->'owner_review_v1'; p:=a.metadata->'publish_contract_v2';
 reason:=public.dufynd_content_publish_contract_v2_reason(a.metadata,a.platform,c->>'caption');
 if reason is not null then return jsonb_build_object('ready',false,'reason',reason); end if;
 select * into d from public.dufynd_human_decisions where decision_id=w.owner_decision_id;
 if d.status is distinct from 'approved' or d.action_type is distinct from 'content_candidate_review'
  or d.context->'candidate'->>'revision_fingerprint' is distinct from fp
  or d.context->'candidate'->>'asset_reference' is distinct from a.id then
  return jsonb_build_object('ready',false,'reason','review_owner_go_missing'); end if;
 if a.status not in ('internally_ready','ready_to_publish') or c->'internal_ready' is distinct from 'true'::jsonb
  or c->>'platform' is distinct from a.platform or c->>'content_id' is distinct from a.content_id
  or a.metadata->>'review_asset_sha256' is distinct from a.metadata->>'asset_sha256'
  or coalesce(a.metadata->>'asset_sha256','') !~ '^[a-f0-9]{64}$' then
  return jsonb_build_object('ready',false,'reason','frozen_candidate_invalid'); end if;
 if a.platform not in ('instagram','tiktok','youtube')
  or p->'audio_contract'->>'mode' is distinct from 'embedded_video'
  or p->'audio_contract'->>'delivery' is distinct from 'metricool_auto'
  or (a.platform='instagram' and p->>'media_kind' is distinct from 'reel')
  or (a.platform in ('tiktok','youtube') and p->>'media_kind' is distinct from 'video') then
  return jsonb_build_object('ready',false,'reason','embedded_automatic_video_required'); end if;
 if a.uri !~ '^https://' or position(a.metadata->>'asset_sha256' in a.uri)=0
  or a.metadata->'immutable_media_verified' is distinct from 'true'::jsonb
  or coalesce(a.metadata->>'immutable_media_evidence_ref','')='' then
  return jsonb_build_object('ready',false,'reason','immutable_content_addressed_media_required'); end if;
 if public.dufynd_parse_timestamp(c->>'requested_at') is null
  or public.dufynd_parse_timestamp(c->>'requested_at')<=now() then
  return jsonb_build_object('ready',false,'reason','requested_time_missing_or_past'); end if;
 if jsonb_typeof(a.metadata->'release_contract_v1') is distinct from 'object'
  or nullif(trim(a.metadata->'release_contract_v1'->>'title'),'') is null
  or length(a.metadata->'release_contract_v1'->>'title')>100
  or jsonb_typeof(a.metadata->'release_contract_v1'->'ai_generated') is distinct from 'boolean'
  or nullif(trim(a.metadata->'release_contract_v1'->>'audio_source'),'') is null
  or nullif(trim(a.metadata->'release_contract_v1'->>'visual_rights_evidence_ref'),'') is null
  or a.metadata->'release_contract_v1'->'commercial_visual_rights_verified' is distinct from 'true'::jsonb
  or (a.metadata->'release_contract_v1'->'ai_generated'='true'::jsonb and not (coalesce(c->>'caption','') ~* '(KI|AI)[ -]')) then
  return jsonb_build_object('ready',false,'reason','title_ai_source_or_visual_rights_missing'); end if;
 return jsonb_build_object('ready',true,'publishing_authorized',false,'asset_id',a.id,
  'revision_fingerprint',fp,'asset_sha256',a.metadata->>'asset_sha256','uri',a.uri,
  'content_id',a.content_id,'platform',a.platform,'brand_id','7182186','caption',c->>'caption',
  'requested_at',c->>'requested_at','maker_id',a.metadata->>'creator_actor_id', 'title',a.metadata->'release_contract_v1'->>'title', 'ai_generated',a.metadata->'release_contract_v1'->'ai_generated', 'audio_source',a.metadata->'release_contract_v1'->>'audio_source', 'audio_rights_evidence_ref',p->'audio_contract'->>'commercial_rights_evidence_ref');
end $$;


alter table public.dufynd_publish_dispatches drop constraint dufynd_publish_dispatches_platform_check;
alter table public.dufynd_publish_dispatches add constraint dufynd_publish_dispatches_platform_check check(platform in ('instagram','tiktok','youtube'));
create table public.dufynd_content_releases (
 release_id text primary key, content_id text not null unique,
 kind text not null check(kind in ('short','photo')),
 halted boolean not null default false, blocker text,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.dufynd_release_platforms (
 release_id text not null references public.dufynd_content_releases(release_id),
 platform text not null check(platform in ('youtube','instagram','tiktok')),
 asset_id text not null unique references public.dufynd_content_assets(id),
 status text not null default 'BLOCKED' check(status in ('READY','BLOCKED','SCHEDULED','PUBLISHED','AUDIO_VERIFIED','FAILED')),
 blocker text, dispatch_id uuid unique references public.dufynd_publish_dispatches(dispatch_id),
 packet jsonb, evidence jsonb not null default '{}', updated_at timestamptz not null default now(),
 primary key(release_id,platform)
);
alter table public.dufynd_content_releases enable row level security;
alter table public.dufynd_release_platforms enable row level security;
revoke all on public.dufynd_content_releases,public.dufynd_release_platforms from public,anon,authenticated;
grant select,insert,update on public.dufynd_content_releases,public.dufynd_release_platforms to service_role;

create function public.register_dufynd_release_v1(p_release_id text,p_content_id text,p_kind text,p_assets jsonb)
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
  if not exists(select 1 from public.dufynd_content_assets where id=row.value and platform=row.key and content_id=p_content_id
   and (p_kind<>'short' or coalesce(metadata->'publish_contract_v2'->>'media_kind','')=case row.key when 'instagram' then 'reel' else 'video' end)
   and (p_kind<>'photo' or coalesce(metadata->'publish_contract_v2'->>'media_kind','') in ('image','carousel'))) then raise exception 'asset_platform_content_or_format_mismatch'; end if;
  insert into public.dufynd_release_platforms(release_id,platform,asset_id,blocker) values(p_release_id,row.key,row.value,'preflight_required') on conflict do nothing;
  if not exists(select 1 from public.dufynd_release_platforms where release_id=p_release_id and platform=row.key and asset_id=row.value) then raise exception 'release_asset_replacement_forbidden'; end if;
 end loop;
 return jsonb_build_object('registered',true,'publishing_authorized',false);
end $$;

create function public.preflight_dufynd_release_v1(p_release_id text,p_decisions jsonb default '{}') returns jsonb
language plpgsql security invoker set search_path=public as $$
<<fn>>
declare r public.dufynd_content_releases; row record; packet jsonb; d public.dufynd_human_decisions;
 reason text; results jsonb:='{}'; all_ready boolean:=true; expected int; actual int;
begin
 select * into r from public.dufynd_content_releases where release_id=p_release_id for update;
 if not found then return jsonb_build_object('ready',false,'reason','release_missing','platforms','{}'::jsonb); end if;
 expected:=case r.kind when 'short' then 3 else 2 end;
 select count(*) into actual from public.dufynd_release_platforms where release_id=p_release_id;
 for row in select * from public.dufynd_release_platforms where release_id=p_release_id order by platform for update loop
  packet:=public.read_dufynd_publish_packet_v1(row.asset_id); reason:=null;
  if r.halted then reason:=coalesce(r.blocker,'release_halted');
  elsif row.dispatch_id is not null then reason:='duplicate_or_uncertain_dispatch';
  elsif r.kind='photo' then reason:='photo_native_handoff_required';
  elsif packet->'ready' is distinct from 'true'::jsonb then reason:=packet->>'reason';
  else
   select * into d from public.dufynd_human_decisions where decision_id=p_decisions->>row.platform;
   if not found or d.status is distinct from 'approved' or d.action_type is distinct from 'content_publish_go'
    or d.context->>'scope' is distinct from 'schedule_and_publish' or d.context->'candidate' is distinct from packet
    or d.decision->>'source' is distinct from 'private_control_room' or d.decision->'owner_confirmed' is distinct from 'true'::jsonb
    or d.decision->>'action' is distinct from 'approve' or d.decision->'review_only' is distinct from 'false'::jsonb then reason:='specific_owner_publish_go_required'; end if;
  end if;
  if reason is not null then all_ready:=false; end if;
  if row.dispatch_id is null then
   update public.dufynd_release_platforms set status=case when reason is null then 'READY' else 'BLOCKED' end,
    blocker=reason,packet=fn.packet,updated_at=now() where release_id=p_release_id and platform=row.platform;
  end if;
  results:=results||jsonb_build_object(row.platform,jsonb_build_object('ready',reason is null,'reason',reason,'packet',packet,'status',case when row.dispatch_id is not null then row.status when reason is null then 'READY' else 'BLOCKED' end));
 end loop;
 return jsonb_build_object('ready',all_ready and actual=expected,'reason',case when actual<>expected then 'all_expected_platforms_required' end,'platforms',results,'publishing_authorized',false);
end $$;

create function public.reserve_dufynd_release_v1(p_release_id text,p_decisions jsonb,p_packets jsonb) returns jsonb
language plpgsql security invoker set search_path=public as $$
<<fn>>
declare pre jsonb; row record; packet jsonb; dispatch uuid; reserved jsonb:='{}';
begin
 perform 1 from public.dufynd_content_releases where release_id=p_release_id for update;
 -- Deterministic locks serialize edits and revocation against all-platform GO.
 perform 1 from public.dufynd_content_assets where id in (select asset_id from public.dufynd_release_platforms where release_id=p_release_id) order by id for update;
 perform 1 from public.dufynd_human_decisions where decision_id in (select value from jsonb_each_text(p_decisions)) order by decision_id for update;
 pre:=public.preflight_dufynd_release_v1(p_release_id,p_decisions);
 if pre->'ready' is distinct from 'true'::jsonb then return pre||jsonb_build_object('reserved',false); end if;
 for row in select * from public.dufynd_release_platforms where release_id=p_release_id order by platform loop
  packet:=pre->'platforms'->row.platform->'packet';
  if packet is distinct from p_packets->row.platform then return jsonb_build_object('reserved',false,'reason','asset_or_revision_changed'); end if;
  if exists(select 1 from public.dufynd_publish_dispatches where brand_id='7182186' and platform=row.platform and (content_id=packet->>'content_id' or asset_sha256=packet->>'asset_sha256')) then
   return jsonb_build_object('reserved',false,'reason','duplicate_or_uncertain_dispatch'); end if;
 end loop;
 -- All reservations happen in this transaction BEFORE any irreversible call.
 for row in select * from public.dufynd_release_platforms where release_id=p_release_id order by platform loop
  packet:=pre->'platforms'->row.platform->'packet';
  insert into public.dufynd_publish_dispatches(asset_id,revision_fingerprint,asset_sha256,content_id,platform,brand_id,owner_decision_id)
   values(row.asset_id,packet->>'revision_fingerprint',packet->>'asset_sha256',packet->>'content_id',row.platform,'7182186',p_decisions->>row.platform) returning dispatch_id into dispatch;
  update public.dufynd_release_platforms set dispatch_id=dispatch,packet=fn.packet,status='BLOCKED',blocker='reserved_awaiting_provider_receipt',updated_at=now() where release_id=p_release_id and platform=row.platform;
  reserved:=reserved||jsonb_build_object(row.platform,jsonb_build_object('dispatch_id',dispatch,'packet',packet));
 end loop;
 return jsonb_build_object('reserved',true,'platforms',reserved);
end $$;

-- Fail closed for old per-platform callers. Existing decisions are preserved.
create or replace function public.reserve_dufynd_publish_v1(p_asset_id text,p_revision_fingerprint text,p_asset_sha256 text,p_decision_id text)
returns jsonb language sql security invoker set search_path=public as $$ select jsonb_build_object('reserved',false,'reason','release_dispatch_required') $$;

create or replace function public.record_dufynd_publish_receipt_v1(p_dispatch_id uuid,p_state text,p_receipt jsonb) returns boolean
language plpgsql security invoker set search_path=public as $$
<<fn>>
declare rid text;
begin
 if p_state not in ('scheduled','outcome_unknown') or jsonb_typeof(p_receipt) is distinct from 'object' or octet_length(p_receipt::text)>24000 then return false; end if;
 if p_state='scheduled' and (coalesce(p_receipt->>'provider_post_id','')='' or p_receipt->'exact_media_uri_echoed' is distinct from 'true'::jsonb) then return false; end if;
 select release_id into rid from public.dufynd_release_platforms where dispatch_id=p_dispatch_id;
 perform 1 from public.dufynd_content_releases where release_id=rid for update;
 update public.dufynd_publish_dispatches set state=p_state,receipt=p_receipt,updated_at=now() where dispatch_id=p_dispatch_id and state='dispatch_started';
 if not found then return false; end if;
 update public.dufynd_release_platforms set status=case p_state when 'scheduled' then 'SCHEDULED' else 'FAILED' end,
  blocker=case when p_state='outcome_unknown' then 'reconcile_provider_before_any_retry' end,evidence=p_receipt,updated_at=now() where dispatch_id=p_dispatch_id;
 if p_state='outcome_unknown' then
  update public.dufynd_content_releases set halted=true,blocker='partial_or_unknown_outcome_reconcile_no_retry',updated_at=now() where release_id=rid;
  update public.dufynd_release_platforms set status='BLOCKED',blocker='release_halted_no_retry',updated_at=now() where release_id=rid and status='READY';
 end if;
 return true;
end $$;

create function public.record_dufynd_release_publication_v1(p_release_id text,p_platform text,p_state text,p_evidence jsonb) returns boolean
language plpgsql security invoker set search_path=public as $$
<<fn>>
declare row public.dufynd_release_platforms; url text:=p_evidence->>'public_url'; native text:=p_evidence->>'platform_post_id';
begin
 select * into row from public.dufynd_release_platforms where release_id=p_release_id and platform=p_platform for update;
 if not found or row.status not in ('SCHEDULED','PUBLISHED') or p_state not in ('PUBLISHED','AUDIO_VERIFIED') then return false; end if;
 if p_evidence->>'source_sha256' is distinct from row.packet->>'asset_sha256'
  or coalesce(p_evidence->>'platform_output_sha256','') !~ '^[a-f0-9]{64}$'
  or p_evidence->'media_identity_verified' is distinct from 'true'::jsonb
  or coalesce(p_evidence->>'evidence_ref','')='' or coalesce(p_evidence->>'checker_id','')=''
  or p_evidence->>'checker_id' is not distinct from row.packet->>'maker_id' then return false; end if;
 if (p_platform='youtube' and (coalesce(native,'') !~ '^[A-Za-z0-9_-]{11}$' or url is distinct from 'https://www.youtube.com/shorts/'||native))
  or (p_platform='tiktok' and (coalesce(native,'') !~ '^[0-9]{5,30}$' or coalesce(url,'') !~ ('^https://www[.]tiktok[.]com/@[A-Za-z0-9._]+/video/'||native||'/?$')))
  or (p_platform='instagram' and (coalesce(native,'') !~ '^[0-9]{5,30}$' or coalesce(url,'') !~ '^https://www[.]instagram[.]com/(p|reel)/[A-Za-z0-9_-]+/?$')) then return false; end if;
 if row.status='PUBLISHED' and (row.evidence->>'platform_post_id' is distinct from native or row.evidence->>'public_url' is distinct from url or row.evidence->>'platform_output_sha256' is distinct from p_evidence->>'platform_output_sha256') then return false; end if;
 if p_state='AUDIO_VERIFIED' and (row.status<>'PUBLISHED' or p_evidence->'audible_playback_verified' is distinct from 'true'::jsonb
  or p_evidence->'full_decode_passed' is distinct from 'true'::jsonb or p_evidence->'timing_verified' is distinct from 'true'::jsonb or p_evidence->'audio_match_verified' is distinct from 'true'::jsonb) then return false; end if;
 update public.dufynd_release_platforms set status=p_state,evidence=evidence||p_evidence,blocker=null,updated_at=now() where release_id=p_release_id and platform=p_platform;
 return true;
end $$;

revoke all on function public.register_dufynd_release_v1(text,text,text,jsonb),public.preflight_dufynd_release_v1(text,jsonb),public.reserve_dufynd_release_v1(text,jsonb,jsonb),public.record_dufynd_release_publication_v1(text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.register_dufynd_release_v1(text,text,text,jsonb),public.preflight_dufynd_release_v1(text,jsonb),public.reserve_dufynd_release_v1(text,jsonb,jsonb),public.record_dufynd_release_publication_v1(text,text,text,jsonb) to service_role;

create function public.claim_dufynd_release_dispatch_v1(p_dispatch_id uuid) returns boolean
language plpgsql security invoker set search_path=public as $$
<<fn>>
declare row public.dufynd_release_platforms; d public.dufynd_human_decisions;
begin
 select * into row from public.dufynd_release_platforms where dispatch_id=p_dispatch_id;
 if not found then return false; end if;
 perform 1 from public.dufynd_content_releases where release_id=row.release_id and not halted for update;
 if not found then return false; end if;
 perform 1 from public.dufynd_content_assets where id=row.asset_id for update;
 if public.dufynd_content_revision(row.asset_id) is distinct from row.packet->>'revision_fingerprint' then return false; end if;
 select h.* into d from public.dufynd_human_decisions h join public.dufynd_publish_dispatches p on p.owner_decision_id=h.decision_id where p.dispatch_id=p_dispatch_id for update of h;
 if d.status is distinct from 'approved' or d.context->'candidate' is distinct from row.packet
  or d.decision->>'action' is distinct from 'approve' or d.decision->'owner_confirmed' is distinct from 'true'::jsonb
  or d.decision->'review_only' is distinct from 'false'::jsonb or d.decision->>'source' is distinct from 'private_control_room' then return false; end if;
 update public.dufynd_publish_dispatches set receipt='{"invocation_claimed":true}',updated_at=now()
  where dispatch_id=p_dispatch_id and state='dispatch_started' and receipt='{}'::jsonb;
 return found;
end $$;
revoke all on function public.claim_dufynd_release_dispatch_v1(uuid) from public,anon,authenticated;
grant execute on function public.claim_dufynd_release_dispatch_v1(uuid) to service_role;
