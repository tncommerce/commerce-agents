-- Delina is a TEST FIXTURE only. Roll back all rows and decisions.
begin;
do $$
declare meta jsonb; r jsonb; did text; n int;
begin
 meta:=jsonb_build_object('quality_review','pass','visual_qa','pass','rights_review','pass','product_match_review','pass',
 'destination_review','pass','asset_sha256',repeat('a',64),'review_asset_sha256',repeat('a',64),
 'review_evidence_ref','qa_review_fixture','creator_actor_id','qa_creator','internal_reviewer_actor_id','qa_independent_checker',
 'campaign_id','qa_delina_gate','product_id','SC-PDM-DELINA-EDP-75','owner_review_v1',jsonb_build_object(
 'internal_ready',true,'product','Parfums de Marly Delina EDP 75 ml','product_id','SC-PDM-DELINA-EDP-75',
 'hook','Delina: passt sie zu deinem Duftprofil?','caption','Duftprofil und Kaufoptionen auf DUFYND. Testfixture, kein Publishing.',
 'reason','Complete review fixture for a gated next candidate.','platform','instagram','requested_at',now()+interval '1 day',
 'content_id','qa_delina_gate_fixture','experiment_id','qa_delina_gate','internal_rating',9.6));
 select count(*) into n from public.dufynd_human_decisions where status='pending';
 insert into public.dufynd_content_assets(id,asset_type,platform,uri,status,content_id,metadata)
 values('qa_delina_gate_asset','image','instagram','fixture://not-a-real-creative','internally_ready','qa_delina_gate_fixture',meta);
 r:=public.request_dufynd_content_owner_review('qa_delina_gate_asset');
 if r->>'ready'<>'true' or r->>'state'<>'pending' or r->>'publishing_authorized'<>'false' then raise exception 'candidate did not stop at Owner'; end if;
 did:=r->>'decision_id';
 if (select count(*) from public.dufynd_human_decisions where status='pending')<>n+1 then raise exception 'duplicate gate'; end if;
 if not exists(select 1 from public.dufynd_human_decisions where decision_id=did and context->'candidate'->>'caption' is not null
 and context->'candidate'->>'internal_rating'='9.6' and context->>'approval_alone_enables_execution'='false') then raise exception 'review packet missing'; end if;
 update public.dufynd_content_assets set metadata=jsonb_set(metadata,'{owner_review_v1,hook}','"Revised hook requires a new revision review"') where id='qa_delina_gate_asset';
 if (select status from public.dufynd_human_decisions where decision_id=did)<>'superseded' then raise exception 'old revision approval not invalidated'; end if;
 update public.dufynd_content_assets set metadata=jsonb_set(metadata,'{rights_review}','"fail"') where id='qa_delina_gate_asset';
 r:=public.request_dufynd_content_owner_review('qa_delina_gate_asset');
 if r->>'ready'<>'false' or (select count(*) from public.dufynd_human_decisions where status='pending')<>n then raise exception 'rating overrode rights or stale gate survived'; end if;
 update public.dufynd_content_assets set metadata=jsonb_set(meta,'{internal_reviewer_actor_id}','"qa_creator"') where id='qa_delina_gate_asset';
 if public.request_dufynd_content_owner_review('qa_delina_gate_asset')->>'ready'<>'false' then raise exception 'self review accepted'; end if;
 update public.dufynd_content_assets set metadata=jsonb_set(meta,'{owner_review_v1,internal_rating}','5') where id='qa_delina_gate_asset';
 if public.request_dufynd_content_owner_review('qa_delina_gate_asset')->>'ready'<>'false' then raise exception 'substandard asset accepted'; end if;
 if has_function_privilege('anon','public.request_dufynd_content_owner_review(text)','execute')
 or has_function_privilege('authenticated','public.request_dufynd_content_owner_review(text)','execute') then raise exception 'public write endpoint'; end if;
end $$;
rollback;
