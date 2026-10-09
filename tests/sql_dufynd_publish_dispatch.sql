-- Fixture-only claims. Run inside a transaction and ROLLBACK on live DB.
do $$
declare aid text:='qa_publish_'||replace(gen_random_uuid()::text,'-','');
 cid text:='qa_content_'||replace(gen_random_uuid()::text,'-','');
 sha text:=encode(sha256(convert_to(aid,'UTF8')),'hex');
 meta jsonb; checks jsonb:='{}'; fp text; did text; packet jsonb; r jsonb; dispatch uuid; k text;
begin
 meta:=jsonb_build_object('asset_sha256',sha,'review_asset_sha256',sha,
 'creator_actor_id','fixture-maker','internal_reviewer_actor_id','fixture-checker',
 'review_evidence_ref','qa:fixture','campaign_id','qa_campaign','product_id','SC-TEST-100','content_kind','meme',
 'immutable_media_verified',true,'immutable_media_evidence_ref','qa:immutable-fixture',
 'quality_review','pass','visual_qa','pass','rights_review','pass','product_match_review','pass','destination_review','pass',
 'owner_review_v1',jsonb_build_object('internal_ready',true,'product','Fixture only','product_id','SC-TEST-100',
  'hook','Fixture','caption','Fixture only','reason','Disposable test','platform','instagram',
  'requested_at','2099-01-01T10:00:00+01:00','content_id',cid,'experiment_id','qa_campaign','internal_rating',9.7),
 'publish_contract_v2',jsonb_build_object('media_kind','reel','width_px',1080,'height_px',1920,'visual_score',9.7,
  'native_preview_verified',true,'final_upload_asset_verified',true,'cta_mode','profile_link','profile_link_verified',true,
  'genuine_motion_verified',true,'audio_contract',jsonb_build_object('mode','embedded_video','delivery','metricool_auto',
   'commercial_rights_evidence_ref','qa:rights','audible_preview_evidence_ref','qa:listen','audible_preview_verified',true,
   'commercial_music_rights_verified',true,'audio_score',9.7,'final_video_sha256',sha,'audio_codec','aac',
   'audio_stream_evidence_ref','qa:probe','full_playback_verified',true,'timing_verified',true,'loudness_verified',true)),
 'publication_checks_v3','{}'::jsonb);
 for k in select unnest(array['duplicate_content','safe_zones','sharpness_compression','platform_caption','sound_timing']) loop
  meta:=jsonb_set(meta,array['publication_checks_v3',k],jsonb_build_object('passed',true,'asset_sha256',sha,'evidence_ref','qa:fixture'));
 end loop;
 insert into dufynd_content_assets(id,asset_type,version,uri,content_id,platform,status,metadata)
  values(aid,'hero_video_master',1,'https://assets.example.org/'||sha||'.mp4',cid,'instagram','internally_ready',meta);
 fp:=dufynd_content_revision(aid);
 if read_dufynd_publish_packet_v1(aid)->>'reason' is distinct from 'review_workflow_not_owner_approved' then raise exception 'unmanaged asset bypass'; end if;
 for k in select unnest(array['product_truth','rights','product_fidelity','dimensions','mobile_preview','factual_copy','click_path','visual_quality']) loop
  checks:=checks||jsonb_build_object(k,jsonb_build_object('status','pass','revision_fingerprint',fp,'observed_at','2026-01-01T00:00:00Z','evidence_ref','qa:fixture','score',9.7));
 end loop;
 insert into dufynd_human_decisions(decision_id,status,action_type,title,question,decision_token,context)
  values(aid||':review','approved','content_candidate_review','Fixture only','Disposable SQL test','GO-FIXTURE-ONLY',jsonb_build_object('candidate',jsonb_build_object('asset_reference',aid,'revision_fingerprint',fp)));
 insert into dufynd_content_workflows(asset_id,state,revision_fingerprint,evidence,owner_decision_id)
  values(aid,'owner_approved',fp,checks,aid||':review');
 packet:=read_dufynd_publish_packet_v1(aid);
 if packet->'ready' is distinct from 'true'::jsonb then raise exception 'fixture rejected: %',packet; end if;
 if reserve_dufynd_publish_v1(aid,fp,sha,aid||':review')->>'reason' is distinct from 'specific_owner_publish_go_required' then raise exception 'review-only permission bypass'; end if;
 r:=request_dufynd_publish_go_v1(aid); did:=r->>'decision_id';
 if r->'publishing_authorized' is distinct from 'false'::jsonb then raise exception 'request authorized publishing'; end if;
 if reserve_dufynd_publish_v1(aid,fp,sha,did)->>'reason' is distinct from 'specific_owner_publish_go_required' then raise exception 'pending GO bypass'; end if;
 update dufynd_human_decisions set status='approved',decision='{"owner_confirmed":true,"action":"approve_review","review_only":true,"source":"private_control_room"}' where decision_id=did;
 if reserve_dufynd_publish_v1(aid,fp,sha,did)->>'reason' is distinct from 'specific_owner_publish_go_required' then raise exception 'review action bypass'; end if;
 update dufynd_human_decisions set decision='{"owner_confirmed":true,"action":"approve","review_only":false,"source":"private_control_room"}' where decision_id=did;
 if reserve_dufynd_publish_v1(aid,fp,repeat('b',64),did)->>'reason' is distinct from 'asset_or_revision_changed' then raise exception 'changed bytes bypass'; end if;
 r:=reserve_dufynd_publish_v1(aid,fp,sha,did);
 if r->'reserved' is distinct from 'true'::jsonb then raise exception 'fixture reserve failed: %',r; end if;
 dispatch:=(r->>'dispatch_id')::uuid;
 if reserve_dufynd_publish_v1(aid,fp,sha,did)->>'reason' is distinct from 'duplicate_or_uncertain_dispatch' then raise exception 'duplicate dispatch'; end if;
 if record_dufynd_publish_receipt_v1(dispatch,'published','{}') then raise exception 'receipt faked public success'; end if;
 if record_dufynd_publish_receipt_v1(dispatch,'scheduled','{}') then raise exception 'missing provider ID accepted'; end if;
 if not record_dufynd_publish_receipt_v1(dispatch,'outcome_unknown','{"reason":"fixture timeout"}') then raise exception 'unknown not recorded'; end if;
 if record_dufynd_publish_receipt_v1(dispatch,'scheduled','{"provider_post_id":"fake"}') then raise exception 'unknown retried'; end if;
 if reserve_dufynd_publish_v1(aid,fp,sha,did)->>'reason' is distinct from 'duplicate_or_uncertain_dispatch' then raise exception 'uncertain dispatch retried'; end if;
 update dufynd_content_assets set version=2 where id=aid;
 if read_dufynd_publish_packet_v1(aid)->'ready' is distinct from 'false'::jsonb then raise exception 'changed revision accepted'; end if;
 if has_function_privilege('anon','reserve_dufynd_publish_v1(text,text,text,text)','execute')
 or has_function_privilege('authenticated','request_dufynd_publish_go_v1(text)','execute')
 or has_table_privilege('anon','dufynd_publish_dispatches','select') then raise exception 'publisher privilege leak'; end if;
end $$;
