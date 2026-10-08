-- Deterministic contracts only; fixture claims are not real listening or music licences.
-- No live asset, decision, scheduling or publication is created.
do $$
declare m jsonb; base jsonb; a jsonb; r text; k text;
begin
 a:=jsonb_build_object('mode','embedded_video','delivery','metricool_auto',
 'commercial_rights_evidence_ref','fixture:rights','audible_preview_evidence_ref','fixture:listen',
 'audible_preview_verified',true,'commercial_music_rights_verified',true,'audio_score',9.7,
 'final_video_sha256',repeat('a',64),'audio_codec','aac','audio_stream_evidence_ref','fixture:ffprobe',
 'full_playback_verified',true,'timing_verified',true,'loudness_verified',true);
 base:=jsonb_build_object('content_kind','meme','asset_sha256',repeat('a',64),
 'publish_contract_v2',jsonb_build_object('media_kind','reel','width_px',1080,'height_px',1920,
 'visual_score',9.7,'native_preview_verified',true,'final_upload_asset_verified',true,
 'cta_mode','profile_link','profile_link_verified',true,'genuine_motion_verified',true,'audio_contract',a));
 base:=base||jsonb_build_object('publication_checks_v3','{}'::jsonb);
 for k in select unnest(array['duplicate_content','safe_zones','sharpness_compression','platform_caption','sound_timing']) loop
  base:=jsonb_set(base,array['publication_checks_v3',k],jsonb_build_object('passed',true,'asset_sha256',repeat('a',64),'evidence_ref','fixture:quality'));
 end loop;
 if public.dufynd_content_publish_contract_v2_reason(base,'instagram','fixture caption') is not null then raise exception 'complete embedded fixture rejected'; end if;
 m:=jsonb_set(base,'{publish_contract_v2,media_kind}','"video"');
 m:=jsonb_set(m,'{publish_contract_v2,cta_mode}','"engagement"');
 if public.dufynd_content_publish_contract_v2_reason(m,'tiktok','fixture caption') is not null then raise exception 'complete tiktok fixture rejected'; end if;
 m:=base#-'{publish_contract_v2,audio_contract}';
 if public.dufynd_content_publish_contract_v2_reason(m,'instagram','fixture caption') is distinct from 'audio_contract_required' then raise exception 'missing audio bypass'; end if;
 for k in select unnest(array['audible_preview_verified','commercial_music_rights_verified','full_playback_verified','timing_verified','loudness_verified']) loop
  m:=jsonb_set(base,array['publish_contract_v2','audio_contract',k],'false');
  if public.dufynd_content_publish_contract_v2_reason(m,'instagram','fixture caption') is null then raise exception 'false evidence bypass: %',k; end if;
  m:=jsonb_set(base,array['publish_contract_v2','audio_contract',k],'"true"');
  if public.dufynd_content_publish_contract_v2_reason(m,'instagram','fixture caption') is null then raise exception 'string boolean bypass: %',k; end if;
 end loop;
 m:=jsonb_set(base,'{publish_contract_v2,audio_contract,final_video_sha256}',to_jsonb(repeat('b',64)));
 if public.dufynd_content_publish_contract_v2_reason(m,'instagram','fixture caption') is distinct from 'embedded_audio_video_digest_mismatch' then raise exception 'different video bypass'; end if;
 m:=jsonb_set(base,'{publish_contract_v2,height_px}','1080');
 if public.dufynd_content_publish_contract_v2_reason(m,'instagram','fixture caption') is distinct from 'video_requires_1080x1920_9_16' then raise exception 'square reel bypass'; end if;
 m:=jsonb_set(base,'{publish_contract_v2,genuine_motion_verified}','false');
 if public.dufynd_content_publish_contract_v2_reason(m,'instagram','fixture caption') is distinct from 'genuine_video_motion_not_verified' then raise exception 'fake reel bypass'; end if;
 m:=jsonb_set(base,'{publish_contract_v2,audio_contract,mode}','"intentional_silence"');
 if public.dufynd_content_publish_contract_v2_reason(m,'instagram','fixture caption') is distinct from 'silent_meme_forbidden' then raise exception 'silent meme bypass'; end if;
 m:=jsonb_set(base,'{publish_contract_v2,audio_contract,mode}','"metricool_reel_library"');
 if public.dufynd_content_publish_contract_v2_reason(m,'instagram','fixture caption') is distinct from 'instagram_reel_connection_unverified' then raise exception 'connection bypass'; end if;
 m:=jsonb_set(m,'{publish_contract_v2,audio_contract}',(m#>'{publish_contract_v2,audio_contract}')||jsonb_build_object(
 'facebook_connection_verified',true,'instagram_business_verified',true,'connection_evidence_ref','fixture:connection',
 'audio_id','1234','native_track_selected_and_preheard',true));
 if public.dufynd_content_publish_contract_v2_reason(m,'instagram','fixture caption') is not null then raise exception 'library fixture rejected'; end if;
 m:=jsonb_set(m,'{publish_contract_v2,media_kind}','"image"');
 if public.dufynd_content_publish_contract_v2_reason(m,'instagram','fixture caption') is distinct from 'instagram_photo_audio_requires_native_handoff' then raise exception 'music attached to image bypass'; end if;
 if has_function_privilege('anon','public.dufynd_content_audio_v3_reason(jsonb,text)','execute')
 or has_function_privilege('authenticated','public.dufynd_content_audio_v3_reason(jsonb,text)','execute') then raise exception 'public audio RPC'; end if;
 for k in select unnest(array['duplicate_content','safe_zones','sharpness_compression','platform_caption','sound_timing']) loop
  m:=base#-array['publication_checks_v3',k];
  if public.dufynd_content_publish_contract_v2_reason(m,'instagram','fixture caption') is distinct from 'publication_check_missing_or_failed_'||k then raise exception 'publication check bypass: %',k; end if;
 end loop;
end $$;
