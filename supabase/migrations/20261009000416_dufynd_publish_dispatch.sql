-- Opt-in publisher. Existing review-only approvals NEVER authorize dispatch.
create table public.dufynd_publish_dispatches (
 dispatch_id uuid primary key default gen_random_uuid(),
 asset_id text not null references public.dufynd_content_assets(id),
 revision_fingerprint text not null,
 asset_sha256 text not null check(asset_sha256 ~ '^[a-f0-9]{64}$'),
 content_id text not null,
 platform text not null check(platform in ('instagram','tiktok')),
 brand_id text not null check(brand_id='7182186'),
 owner_decision_id text not null references public.dufynd_human_decisions(decision_id),
 state text not null default 'dispatch_started' check(state in ('dispatch_started','scheduled','outcome_unknown')),
 receipt jsonb not null default '{}',
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(brand_id,platform,content_id), unique(brand_id,platform,asset_sha256)
);
alter table public.dufynd_publish_dispatches enable row level security;
revoke all on public.dufynd_publish_dispatches from public,anon,authenticated;
grant select,insert,update on public.dufynd_publish_dispatches to service_role;

create function public.read_dufynd_publish_packet_v1(p_asset_id text) returns jsonb
language plpgsql stable security invoker set search_path=public as $$
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
 if a.platform not in ('instagram','tiktok')
  or p->'audio_contract'->>'mode' is distinct from 'embedded_video'
  or p->'audio_contract'->>'delivery' is distinct from 'metricool_auto'
  or (a.platform='instagram' and p->>'media_kind' is distinct from 'reel')
  or (a.platform='tiktok' and p->>'media_kind' is distinct from 'video') then
  return jsonb_build_object('ready',false,'reason','embedded_automatic_video_required'); end if;
 if a.uri !~ '^https://' or position(a.metadata->>'asset_sha256' in a.uri)=0
  or a.metadata->'immutable_media_verified' is distinct from 'true'::jsonb
  or coalesce(a.metadata->>'immutable_media_evidence_ref','')='' then
  return jsonb_build_object('ready',false,'reason','immutable_content_addressed_media_required'); end if;
 if public.dufynd_parse_timestamp(c->>'requested_at') is null
  or public.dufynd_parse_timestamp(c->>'requested_at')<=now() then
  return jsonb_build_object('ready',false,'reason','requested_time_missing_or_past'); end if;
 return jsonb_build_object('ready',true,'publishing_authorized',false,'asset_id',a.id,
  'revision_fingerprint',fp,'asset_sha256',a.metadata->>'asset_sha256','uri',a.uri,
  'content_id',a.content_id,'platform',a.platform,'brand_id','7182186','caption',c->>'caption',
  'requested_at',c->>'requested_at','maker_id',a.metadata->>'creator_actor_id');
end $$;

create function public.request_dufynd_publish_go_v1(p_asset_id text) returns jsonb
language plpgsql security invoker set search_path=public as $$
declare packet jsonb; did text; token text;
begin
 -- Serialize against asset edits while constructing the exact Owner question.
 perform 1 from public.dufynd_content_assets where id=p_asset_id for update;
 packet:=public.read_dufynd_publish_packet_v1(p_asset_id);
 if packet->'ready' is distinct from 'true'::jsonb then return packet; end if;
 did:='content-publish:'||p_asset_id||':'||substr(packet->>'revision_fingerprint',1,24);
 token:='GO-PUBLISH-'||upper(substr(packet->>'revision_fingerprint',1,24));
 update public.dufynd_human_decisions set status='superseded',updated_at=now()
  where action_type='content_publish_go' and status in ('pending','approved')
  and context->'candidate'->>'asset_id'=p_asset_id and decision_id<>did;
 insert into public.dufynd_human_decisions(decision_id,action_type,title,question,status,decision_token,context)
 values(did,'content_publish_go','Öffentliche Reel-Veröffentlichung: '||(packet->>'content_id'),
  'Publish this exact MP4, caption, platform and time publicly via Metricool? This is a publishing GO, not a visual review.',
  'pending',token,jsonb_build_object('candidate',packet,'scope','schedule_and_publish',
   'approval_alone_enables_execution',true,'manual_action_required',false,'cost_usd',0,
   'exact_go_answer',token,'publishing_authorized',false,'gate_action_executed',false))
 on conflict(decision_id) do nothing;
 return jsonb_build_object('ready',true,'decision_id',did,'decision_token',token,'publishing_authorized',false);
end $$;

create function public.reserve_dufynd_publish_v1(p_asset_id text,p_revision_fingerprint text,p_asset_sha256 text,p_decision_id text)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare packet jsonb; d public.dufynd_human_decisions; dispatch uuid;
begin
 perform 1 from public.dufynd_content_assets where id=p_asset_id for update;
 packet:=public.read_dufynd_publish_packet_v1(p_asset_id);
 if packet->'ready' is distinct from 'true'::jsonb then return packet; end if;
 if packet->>'revision_fingerprint' is distinct from p_revision_fingerprint
  or packet->>'asset_sha256' is distinct from p_asset_sha256 then
  return jsonb_build_object('reserved',false,'reason','asset_or_revision_changed'); end if;
 select * into d from public.dufynd_human_decisions where decision_id=p_decision_id for update;
 if not found or d.status is distinct from 'approved' or d.action_type is distinct from 'content_publish_go'
  or d.context->>'scope' is distinct from 'schedule_and_publish'
  or d.context->'candidate' is distinct from packet
  or d.decision->>'source' is distinct from 'private_control_room'
  or d.decision->'owner_confirmed' is distinct from 'true'::jsonb
  or d.decision->>'action' is distinct from 'approve'
  or d.decision->'review_only' is distinct from 'false'::jsonb then
  return jsonb_build_object('reserved',false,'reason','specific_owner_publish_go_required'); end if;
 insert into public.dufynd_publish_dispatches(asset_id,revision_fingerprint,asset_sha256,content_id,platform,brand_id,owner_decision_id)
 values(p_asset_id,p_revision_fingerprint,p_asset_sha256,packet->>'content_id',packet->>'platform','7182186',p_decision_id)
 on conflict do nothing returning dispatch_id into dispatch;
 if dispatch is null then return jsonb_build_object('reserved',false,'reason','duplicate_or_uncertain_dispatch'); end if;
 return jsonb_build_object('reserved',true,'dispatch_id',dispatch,'packet',packet);
end $$;

create function public.record_dufynd_publish_receipt_v1(p_dispatch_id uuid,p_state text,p_receipt jsonb) returns boolean
language plpgsql security invoker set search_path=public as $$
begin
 if p_state not in ('scheduled','outcome_unknown') or jsonb_typeof(p_receipt) is distinct from 'object'
  or octet_length(p_receipt::text)>24000 then return false; end if;
 if p_state='scheduled' and coalesce(p_receipt->>'provider_post_id','')='' then return false; end if;
 update public.dufynd_publish_dispatches set state=p_state,receipt=p_receipt,updated_at=now()
  where dispatch_id=p_dispatch_id and state='dispatch_started';
 return found;
end $$;

revoke all on function public.read_dufynd_publish_packet_v1(text),public.request_dufynd_publish_go_v1(text),
 public.reserve_dufynd_publish_v1(text,text,text,text),public.record_dufynd_publish_receipt_v1(uuid,text,jsonb)
 from public,anon,authenticated;
grant execute on function public.read_dufynd_publish_packet_v1(text),public.request_dufynd_publish_go_v1(text),
 public.reserve_dufynd_publish_v1(text,text,text,text),public.record_dufynd_publish_receipt_v1(uuid,text,jsonb) to service_role;
