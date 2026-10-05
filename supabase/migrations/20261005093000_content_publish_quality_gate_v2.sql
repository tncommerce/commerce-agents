-- Social publish quality gate V2.
-- Prevents owner-review creation when the final upload asset, native preview
-- or real platform click path has not been evidenced.

create or replace function public.dufynd_content_publish_contract_v2_reason(
  p_metadata jsonb,
  p_platform text,
  p_caption text
) returns text
language plpgsql stable security invoker set search_path=public as $$
declare
  p jsonb;
  score numeric;
  width_px int;
  height_px int;
  media_kind text;
  cta_mode text;
begin
  p:=p_metadata->'publish_contract_v2';
  if jsonb_typeof(p) is distinct from 'object' then return 'publish_contract_v2_required'; end if;

  if coalesce(p->>'visual_score','') !~ '^[0-9]{1,2}(\.[0-9]{1,2})?$'
     or coalesce(p->>'width_px','') !~ '^[0-9]{3,5}$'
     or coalesce(p->>'height_px','') !~ '^[0-9]{3,5}$' then
    return 'publish_contract_values_invalid';
  end if;
  score:=(p->>'visual_score')::numeric;
  width_px:=(p->>'width_px')::int;
  height_px:=(p->>'height_px')::int;
  media_kind:=lower(coalesce(p->>'media_kind',''));
  cta_mode:=lower(coalesce(p->>'cta_mode',''));

  if score<9.5 or score>10 then return 'visual_score_below_owner_standard'; end if;
  if width_px<1080 or height_px<1080 then return 'media_resolution_below_publish_floor'; end if;
  if p->>'native_preview_verified' is distinct from 'true' then return 'native_preview_not_verified'; end if;
  if p->>'final_upload_asset_verified' is distinct from 'true' then return 'final_upload_asset_not_verified'; end if;

  if p_platform='instagram' then
    if media_kind not in ('image','carousel','reel','story') then return 'instagram_media_kind_invalid'; end if;
    if media_kind in ('image','carousel','reel') and coalesce(p_caption,'') ~* 'https?://' then
      return 'instagram_raw_caption_url_forbidden';
    end if;
    if cta_mode not in ('profile_link','story_link_sticker') then return 'instagram_cta_mode_invalid'; end if;
    if cta_mode='profile_link' and p->>'profile_link_verified' is distinct from 'true' then
      return 'instagram_profile_link_not_verified';
    end if;
    if cta_mode='story_link_sticker' and media_kind<>'story' then
      return 'instagram_story_link_requires_story';
    end if;
  elsif p_platform='tiktok' then
    if media_kind not in ('image','carousel','video') then return 'tiktok_media_kind_invalid'; end if;
    if p->>'clickable_website_link_available' is distinct from 'true' then
      if coalesce(p_caption,'') ~* 'https?://' then return 'tiktok_raw_url_without_clickable_surface'; end if;
      if cta_mode not in ('comment','profile','engagement') then return 'tiktok_nonclickable_cta_invalid'; end if;
    end if;
  elsif p_platform='youtube' then
    if media_kind<>'video' then return 'youtube_video_required'; end if;
    if cta_mode not in ('profile_link','description_link') then return 'youtube_cta_mode_invalid'; end if;
  else
    return 'unsupported_platform';
  end if;

  return null;
end $$;

create or replace function public.request_dufynd_content_owner_review(p_asset_id text) returns jsonb
language plpgsql security invoker set search_path=public as $$
declare
  a public.dufynd_content_assets;
  c jsonb;
  fingerprint text;
  did text;
  token text;
  k text;
  desired timestamptz;
  score numeric;
  publish_reason text;
begin
 if p_asset_id is null or p_asset_id !~ '^[A-Za-z0-9._:-]{1,100}$' then return jsonb_build_object('ready',false,'reason','invalid_asset_reference'); end if;
 select * into a from public.dufynd_content_assets where id=p_asset_id for update;
 if not found then return jsonb_build_object('ready',false,'reason','asset_missing'); end if;
 if octet_length(a.metadata::text)>20000 or length(a.uri)>4000 then
 update public.dufynd_human_decisions set status='superseded',updated_at=now() where action_type='content_candidate_review' and status in ('pending','approved') and context->'candidate'->>'asset_reference'=a.id;
 return jsonb_build_object('ready',false,'reason','packet_too_large'); end if;
 fingerprint:=encode(sha256(convert_to(jsonb_build_array(a.id,a.version,a.uri,a.content_id,a.platform,a.status,a.metadata)::text,'UTF8')),'hex');
 update public.dufynd_human_decisions set status='superseded',updated_at=now()
 where action_type='content_candidate_review' and status in ('pending','approved')
 and context->'candidate'->>'asset_reference'=a.id
 and context->'candidate'->>'revision_fingerprint' is distinct from fingerprint;
 c:=a.metadata->'owner_review_v1';
 if a.status not in ('internally_ready','ready_to_publish') or jsonb_typeof(c) is distinct from 'object'
 or c->>'internal_ready' is distinct from 'true' then return jsonb_build_object('ready',false,'reason','not_internally_ready'); end if;
 for k in select unnest(array['quality_review','visual_qa','rights_review','product_match_review','destination_review']) loop
 if a.metadata->>k is distinct from 'pass' then return jsonb_build_object('ready',false,'reason','missing_or_failed_'||k); end if;
 end loop;
 if coalesce(a.metadata->>'asset_sha256','') !~ '^[a-f0-9]{64}$'
 or a.metadata->>'review_asset_sha256' is distinct from a.metadata->>'asset_sha256'
 or coalesce(a.metadata->>'review_evidence_ref','') !~ '^[A-Za-z0-9._:-]{1,100}$'
 or coalesce(a.metadata->>'creator_actor_id','')=''
 or coalesce(a.metadata->>'internal_reviewer_actor_id','')=''
 or a.metadata->>'creator_actor_id'=a.metadata->>'internal_reviewer_actor_id' then
 return jsonb_build_object('ready',false,'reason','revision_review_evidence_missing'); end if;
 for k in select unnest(array['product','hook','caption','reason']) loop
 if coalesce(length(c->>k),0)=0 or length(c->>k)>2000 then return jsonb_build_object('ready',false,'reason','missing_or_unbounded_'||k); end if;
 end loop;
 if c->>'platform' is null or c->>'platform' not in ('instagram','tiktok','youtube')
 or a.platform is distinct from c->>'platform'
 or coalesce(c->>'product_id','') !~ '^SC-[A-Z0-9-]{1,75}$'
 or c->>'content_id' is distinct from a.content_id
 or coalesce(c->>'content_id','') !~ '^[A-Za-z0-9._:-]{1,80}$'
 or coalesce(c->>'experiment_id','') !~ '^[A-Za-z0-9._:-]{1,80}$'
 or c->>'experiment_id' is distinct from a.metadata->>'campaign_id'
 or c->>'product_id' is distinct from a.metadata->>'product_id'
 or c->>'content_id'='one_million_still_hits_20261004_01' then
 return jsonb_build_object('ready',false,'reason','candidate_identity_or_platform_invalid'); end if;

 publish_reason:=public.dufynd_content_publish_contract_v2_reason(a.metadata,c->>'platform',c->>'caption');
 if publish_reason is not null then
   return jsonb_build_object('ready',false,'reason',publish_reason);
 end if;

 desired:=public.dufynd_parse_timestamp(c->>'requested_at');
 if desired is null or desired<=now() or coalesce(c->>'requested_at','') !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' then return jsonb_build_object('ready',false,'reason','desired_time_missing_or_past'); end if;
 if coalesce(c->>'internal_rating','') !~ '^[0-9]{1,2}(\.[0-9]{1,2})?$' then return jsonb_build_object('ready',false,'reason','rating_missing'); end if;
 score:=(c->>'internal_rating')::numeric;
 if score<9.5 or score>10 then return jsonb_build_object('ready',false,'reason','rating_below_owner_standard'); end if;
 did:='content-review:'||a.id||':'||substr(fingerprint,1,24);
 token:='GO-CONTENT-REVIEW-'||upper(substr(fingerprint,1,24));
 insert into public.dufynd_human_decisions(decision_id,action_type,title,question,status,decision_token,context)
 values(did,'content_candidate_review','Content-Kandidat: '||left(c->>'product',100),
 'Review this exact asset revision. No scheduling or publishing is enabled by this decision.', 'pending',token,
 jsonb_build_object('reason',left(c->>'reason',300),'risk','Final independent Owner review remains required; no external action executed.',
 'cost_usd',0,'benefit','Review a complete internally prepared candidate without opening multiple tools.',
 'exact_go_answer',token,'gate_action_executed',false,'approval_alone_enables_execution',false,
 'scheduling_authorized',false,'publishing_authorized',false,'independent_final_review_required',true,
 'candidate',jsonb_build_object('product',c->>'product','product_id',c->>'product_id','asset_reference',a.id,
 'revision_fingerprint',fingerprint,'hook',c->>'hook','caption',c->>'caption','platform',c->>'platform',
 'requested_at',desired,'content_id',c->>'content_id','experiment_id',c->>'experiment_id',
 'internal_rating',score,'recommendation_reason',c->>'reason')))
 on conflict(decision_id) do nothing;
 return jsonb_build_object('ready',true,'decision_id',did,'state',(select status from public.dufynd_human_decisions where decision_id=did),
 'publishing_authorized',false,'scheduling_authorized',false);
end $$;

revoke all on function public.dufynd_content_publish_contract_v2_reason(jsonb,text,text) from public,anon,authenticated;
grant execute on function public.dufynd_content_publish_contract_v2_reason(jsonb,text,text) to service_role;
