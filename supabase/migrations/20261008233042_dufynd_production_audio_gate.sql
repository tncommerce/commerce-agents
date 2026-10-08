-- Enforce the audio contract in the existing production owner-review and workflow gates.
-- No publisher, public permissions, asset backfill or owner approval is created.
create or replace function public.dufynd_content_audio_v3_reason(m jsonb, platform text)
returns text language plpgsql stable security invoker set search_path=public as $$
declare
 p jsonb:=m->'publish_contract_v2'; a jsonb:=p->'audio_contract';
 kind text:=lower(coalesce(m->>'content_kind',''));
 media text:=lower(coalesce(p->>'media_kind',''));
 mode text:=lower(coalesce(a->>'mode','')); delivery text:=lower(coalesce(a->>'delivery',''));
 k text; proof jsonb; width_px int; height_px int;
begin
 if platform not in ('instagram','tiktok') then return null; end if;
 if kind not in ('meme','editorial','education','product') then return 'social_content_kind_required'; end if;
 if jsonb_typeof(a) is distinct from 'object' then return 'audio_contract_required'; end if;
 if (platform='instagram' and media='reel') or (platform='tiktok' and media='video') then
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
 elsif mode='embedded_video' and ((platform='instagram' and media='reel') or (platform='tiktok' and media='video')) then
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

  return public.dufynd_content_audio_v3_reason(p_metadata,p_platform);
end $$;


create or replace function public.dufynd_content_workflow_qa_reason(p_asset_id text) returns text
language plpgsql stable security invoker set search_path=public as $$
declare w public.dufynd_content_workflows; k text; proof jsonb;
begin
 select * into w from public.dufynd_content_workflows where asset_id=p_asset_id;
 if not found then return null; end if; -- Legacy assets are not enrolled/backfilled.
 if w.revision_fingerprint is distinct from public.dufynd_content_revision(p_asset_id) then return 'qa_revision_changed'; end if;
 for k in select unnest(array['product_truth','rights','product_fidelity','dimensions','mobile_preview','factual_copy','click_path','visual_quality']) loop
  proof:=w.evidence->k;
  if proof->>'status' is distinct from 'pass'
   or proof->>'revision_fingerprint' is distinct from w.revision_fingerprint
   or coalesce(proof->>'evidence_ref','') !~ '^[A-Za-z0-9._:-]{1,100}$'
   or public.dufynd_parse_timestamp(proof->>'observed_at') is null
   or public.dufynd_parse_timestamp(proof->>'observed_at')>now() then return 'qa_missing_or_failed_'||k; end if;
 end loop;
 if coalesce(w.evidence->'visual_quality'->>'score','') !~ '^(9\.[5-9][0-9]?|10(\.0{1,2})?)$' then return 'qa_visual_score_below_9_5'; end if;
 return (select public.dufynd_content_audio_v3_reason(a.metadata,a.platform) from public.dufynd_content_assets a where a.id=p_asset_id);
end $$;

revoke all on function public.dufynd_content_publish_contract_v2_reason(jsonb,text,text),public.dufynd_content_workflow_qa_reason(text) from public,anon,authenticated;
grant execute on function public.dufynd_content_publish_contract_v2_reason(jsonb,text,text),public.dufynd_content_workflow_qa_reason(text) to service_role;

create or replace function public.advance_dufynd_content_workflow(p_asset_id text,p_expected_state text,p_next_state text,p_evidence jsonb default '{}')
returns jsonb language plpgsql security invoker set search_path=public as $$
declare a public.dufynd_content_assets; w public.dufynd_content_workflows; fp text; required text; proof jsonb; reason text; next_allowed text; d public.dufynd_human_decisions;
begin
 if jsonb_typeof(p_evidence) is distinct from 'object' or octet_length(p_evidence::text)>12000 then return jsonb_build_object('advanced',false,'reason','invalid_evidence'); end if;
 select * into a from public.dufynd_content_assets where id=p_asset_id for update;
 if not found then return jsonb_build_object('advanced',false,'reason','asset_missing'); end if;
 fp:=public.dufynd_content_revision(p_asset_id);
 select * into w from public.dufynd_content_workflows where asset_id=p_asset_id for update;
 if not found then
  if p_expected_state is not null or p_next_state is distinct from 'brief_ready' then return jsonb_build_object('advanced',false,'reason','workflow_not_started'); end if;
  insert into public.dufynd_content_workflows(asset_id,state,revision_fingerprint) values(a.id,'brief_ready',fp);
  -- Starting an opt-in managed workflow withdraws any premature legacy review.
  update public.dufynd_human_decisions set status='superseded',updated_at=now()
   where action_type='content_candidate_review' and status in ('pending','approved') and context->'candidate'->>'asset_reference'=a.id;
  return jsonb_build_object('advanced',true,'state','brief_ready','publishing_authorized',false);
 end if;
 if w.state is distinct from p_expected_state then return jsonb_build_object('advanced',false,'reason','state_conflict','state',w.state); end if;
 if w.revision_fingerprint is distinct from fp then
  update public.dufynd_content_workflows set state='brief_ready',revision_fingerprint=fp,evidence='{}',blocker='qa_revision_changed',last_progress_at=now() where asset_id=a.id;
  return jsonb_build_object('advanced',false,'reason','qa_revision_changed','state','brief_ready');
 end if;
 -- Explicit failures trigger bounded internal revision routing, never owner approval.
 if p_next_state='self_review_failed' and w.state in ('creative_received','quality_pass','mobile_preview_pass','click_path_pass') then
  update public.dufynd_content_workflows set state=p_next_state,blocker='internal_qa_failed',last_progress_at=now(),evidence=evidence||p_evidence where asset_id=a.id;
  return jsonb_build_object('advanced',true,'state',p_next_state);
 end if;
 if w.state='self_review_failed' and p_next_state='auto_revision_requested' then
  if w.revision_attempts>=3 then return jsonb_build_object('advanced',false,'reason','revision_limit_reached'); end if;
  update public.dufynd_content_workflows set state=p_next_state,revision_attempts=revision_attempts+1,blocker='approved_free_generator_unavailable',last_progress_at=now(),evidence='{}' where asset_id=a.id;
  return jsonb_build_object('advanced',true,'state',p_next_state,'generator_dispatched',false);
 end if;
 next_allowed:=case w.state when 'brief_ready' then 'product_truth_verified' when 'product_truth_verified' then 'rights_verified'
 when 'rights_verified' then 'creative_requested' when 'creative_requested' then 'creative_received'
 when 'auto_revision_requested' then 'creative_received' when 'creative_received' then 'quality_pass'
 when 'quality_pass' then 'mobile_preview_pass' when 'mobile_preview_pass' then 'click_path_pass'
 when 'click_path_pass' then 'owner_review_ready' when 'owner_review_ready' then 'owner_approved'
 when 'owner_approved' then 'scheduled' when 'scheduled' then 'published' when 'published' then 'publication_verified'
 when 'publication_verified' then 'measurement_active' when 'measurement_active' then 'learning_captured' end;
 if p_next_state is distinct from next_allowed then return jsonb_build_object('advanced',false,'reason','transition_forbidden'); end if;
 if p_next_state='creative_requested' then
  update public.dufynd_content_workflows set state=p_next_state,blocker='approved_free_generator_unavailable',last_progress_at=now() where asset_id=a.id;
  return jsonb_build_object('advanced',true,'state',p_next_state,'generator_dispatched',false);
 end if;
 required:=case p_next_state when 'product_truth_verified' then 'product_truth' when 'rights_verified' then 'rights'
 when 'creative_received' then 'creative_receipt' when 'quality_pass' then 'visual_quality'
 when 'mobile_preview_pass' then 'mobile_preview' when 'click_path_pass' then 'click_path'
 when 'scheduled' then 'schedule_observation' when 'published' then 'publication_observation'
 when 'publication_verified' then 'publication_verification' when 'measurement_active' then 'measurement'
 when 'learning_captured' then 'learning' end;
 if required is not null then
  proof:=p_evidence->required;
  if proof->>'status' is distinct from 'pass' or proof->>'revision_fingerprint' is distinct from fp
   or coalesce(proof->>'evidence_ref','') !~ '^[A-Za-z0-9._:-]{1,100}$'
   or public.dufynd_parse_timestamp(proof->>'observed_at') is null
   or public.dufynd_parse_timestamp(proof->>'observed_at')>now() then return jsonb_build_object('advanced',false,'reason','missing_revision_evidence'); end if;
 end if;
 if p_next_state='publication_verified' and a.platform in ('instagram','tiktok') then
  proof:=p_evidence->'publication_verification';
  if proof->'audio_playback_verified' is distinct from 'true'::jsonb
   or proof->>'asset_sha256' is distinct from a.metadata->>'asset_sha256'
   or coalesce(proof->>'platform_post_id','') !~ '^[0-9]{5,30}$'
   or (a.platform='instagram' and coalesce(proof->>'public_url','') !~ '^https://www[.]instagram[.]com/(p|reel)/[A-Za-z0-9_-]+/?$')
   or (a.platform='tiktok' and coalesce(proof->>'public_url','') !~ '^https://www[.]tiktok[.]com/@[A-Za-z0-9._]+/video/[0-9]+/?$') then
   return jsonb_build_object('advanced',false,'reason','public_audio_playback_evidence_required');
  end if;
 end if;
 if p_next_state='owner_approved' then
  select * into d from public.dufynd_human_decisions where decision_id=w.owner_decision_id;
  if d.status is distinct from 'approved' or d.action_type is distinct from 'content_candidate_review'
   or d.context->'candidate'->>'revision_fingerprint' is distinct from fp
   or d.context->'candidate'->>'asset_reference' is distinct from a.id then return jsonb_build_object('advanced',false,'reason','owner_go_missing'); end if;
 end if;
 update public.dufynd_content_workflows set evidence=evidence||p_evidence where asset_id=a.id;
 if p_next_state in ('quality_pass','owner_review_ready','owner_approved','scheduled','published','publication_verified','measurement_active','learning_captured') then
  reason:=public.dufynd_content_workflow_qa_reason(a.id);
  if reason is not null then
   update public.dufynd_content_workflows set blocker=reason where asset_id=a.id;
   return jsonb_build_object('advanced',false,'reason',reason);
  end if;
 end if;
 if p_next_state='owner_review_ready' then
  proof:=public.request_dufynd_content_owner_review(a.id);
  if proof->>'ready' is distinct from 'true' then return jsonb_build_object('advanced',false,'reason',proof->>'reason'); end if;
  update public.dufynd_content_workflows set owner_decision_id=proof->>'decision_id' where asset_id=a.id;
 end if;
 update public.dufynd_content_workflows set state=p_next_state,blocker=null,last_progress_at=now() where asset_id=a.id;
 return jsonb_build_object('advanced',true,'state',p_next_state,'publishing_authorized',false,'scheduling_authorized',false);
end $$;


revoke all on function public.advance_dufynd_content_workflow(text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.advance_dufynd_content_workflow(text,text,text,jsonb) to service_role;
