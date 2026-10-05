-- Opt-in, revision-bound control state. No assets, approvals or publications are created here.
create table public.dufynd_content_workflows (
 asset_id text primary key references public.dufynd_content_assets(id),
 state text not null check(state in ('brief_ready','product_truth_verified','rights_verified',
 'creative_requested','creative_received','self_review_failed','auto_revision_requested',
 'quality_pass','mobile_preview_pass','click_path_pass','owner_review_ready','owner_approved',
 'scheduled','published','publication_verified','measurement_active','learning_captured')),
 revision_fingerprint text not null check(revision_fingerprint ~ '^[a-f0-9]{64}$'),
 evidence jsonb not null default '{}' check(jsonb_typeof(evidence)='object' and octet_length(evidence::text)<=12000),
 revision_attempts int not null default 0 check(revision_attempts between 0 and 3),
 last_progress_at timestamptz not null default now(),
 blocker text, owner_decision_id text references public.dufynd_human_decisions(decision_id)
);
alter table public.dufynd_content_workflows enable row level security;
revoke all on public.dufynd_content_workflows from public,anon,authenticated;
grant select,insert,update on public.dufynd_content_workflows to service_role;

create function public.dufynd_content_revision(p_asset_id text) returns text
language sql stable security invoker set search_path=public as $$
 select encode(sha256(convert_to(jsonb_build_array(a.id,a.version,a.uri,a.content_id,a.platform,a.status,a.metadata)::text,'UTF8')),'hex')
 from public.dufynd_content_assets a where a.id=p_asset_id;
$$;

create function public.dufynd_content_workflow_qa_reason(p_asset_id text) returns text
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
 return null;
end $$;

create function public.advance_dufynd_content_workflow(p_asset_id text,p_expected_state text,p_next_state text,p_evidence jsonb default '{}')
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
 publish_reason:=public.dufynd_content_workflow_qa_reason(a.id);
 if publish_reason is not null then return jsonb_build_object('ready',false,'reason',publish_reason); end if;
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
 on conflict(decision_id) do update set status=case when public.dufynd_human_decisions.status='superseded' then 'pending' else public.dufynd_human_decisions.status end,updated_at=now();
 return jsonb_build_object('ready',true,'decision_id',did,'state',(select status from public.dufynd_human_decisions where decision_id=did),
 'publishing_authorized',false,'scheduling_authorized',false);
end $$;


revoke all on function public.dufynd_content_revision(text),public.dufynd_content_workflow_qa_reason(text),public.advance_dufynd_content_workflow(text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.dufynd_content_revision(text),public.dufynd_content_workflow_qa_reason(text),public.advance_dufynd_content_workflow(text,text,text,jsonb) to service_role;
