-- Existing inbox is the only event queue. Status remains canonical.
alter table public.dufynd_jarvis_inbox
 add column event_id uuid not null default gen_random_uuid(),
 add column observed_at timestamptz not null default now(),
 add column source_cursor text,
 add column fingerprint text,
 add column related_task_ids jsonb not null default '[]',
 add column processing_status text generated always as (status) stored;
create unique index dufynd_event_fingerprint on public.dufynd_jarvis_inbox(fingerprint) where fingerprint is not null;
create unique index dufynd_event_identity on public.dufynd_jarvis_inbox(event_id);
create table public.dufynd_external_observers (
 observer_id text primary key, source_type text not null check(source_type in ('github_branch','github_pr','github_ci','github_workflow','render','gmail','internal_dependency')),
 source_id text not null, config jsonb not null default '{}', enabled boolean not null default true,
 interval_seconds int not null default 120 check(interval_seconds between 120 and 3600),
 last_attempt_at timestamptz,last_success_at timestamptz,last_cursor text,last_event_at timestamptz,
 consecutive_failures int not null default 0,next_retry_at timestamptz not null default now(),
 health_status text not null default 'initializing' check(health_status in ('initializing','healthy','degraded','stale','blocked_configuration','resync_required')),
 last_error text,last_snapshot jsonb not null default '{}',etag text,page_token text,
 request_id bigint,request_started_at timestamptz,
 unique(source_type,source_id)
);
create table public.dufynd_task_external_waits (
 task_id text not null references public.dufynd_autonomy_tasks(task_id),
 observer_id text not null references public.dufynd_external_observers(observer_id),
 event_types jsonb not null check(jsonb_typeof(event_types)='array' and jsonb_array_length(event_types)>0),
 expected_sha text,policy text not null default 'dependency' check(policy in ('dependency','review','freshness')),
 satisfied boolean not null default false,last_event_id uuid,reevaluated_at timestamptz,
 primary key(task_id,observer_id)
);
create index dufynd_external_wait_observer on public.dufynd_task_external_waits(observer_id);
create index dufynd_dependency_lookup on public.dufynd_autonomy_tasks using gin(dependencies);
alter table public.dufynd_autonomy_tasks add column external_review_required boolean not null default false,
 add column needs_freshness_recheck boolean not null default false,add column durable_payload jsonb,add column last_external_event_id uuid;
alter table public.dufynd_external_observers enable row level security;
alter table public.dufynd_task_external_waits enable row level security;
alter table public.dufynd_jarvis_inbox enable row level security;
revoke all on public.dufynd_external_observers,public.dufynd_task_external_waits from public,anon,authenticated;
grant all on public.dufynd_external_observers,public.dufynd_task_external_waits to service_role;

create function public.register_dufynd_observer(p_type text,p_source_id text,p_config jsonb default '{}',p_baseline jsonb default '{}',p_cursor text default null)
returns text language plpgsql security invoker set search_path=public as $$
declare oid text:=p_type||':'||p_source_id;
begin
 if p_type not in ('github_branch','github_pr','github_ci','github_workflow','render','gmail','internal_dependency')
 or p_type is null or nullif(p_source_id,'') is null or jsonb_typeof(p_config) is distinct from 'object' or jsonb_typeof(p_baseline) is distinct from 'object' then raise exception 'invalid observer'; end if;
 if (p_type='github_branch' and p_source_id<>'scentai-mvp')
 or (p_type in ('github_pr','github_ci','github_workflow') and p_source_id !~ '^[0-9]+$')
 or (p_type='gmail' and p_source_id !~ '^[a-f0-9]{16}$')
 or (p_type='render' and p_source_id !~ '^srv-[a-z0-9]+$') then raise exception 'source is outside allowlist'; end if;
 if p_type='gmail' and p_cursor is not null and p_cursor !~ '^[0-9]+$' then raise exception 'invalid Gmail cursor'; end if;
 insert into public.dufynd_external_observers(observer_id,source_type,source_id,config,last_snapshot,last_cursor)
 values(oid,p_type,p_source_id,p_config,p_baseline,p_cursor) on conflict(observer_id) do nothing;
 -- A retry cannot rewind a cursor or reset health.
 return oid;
end $$;

create function public.dufynd_observer_failure(p_observer_id text,p_error text,p_status int default 0,p_retry_seconds int default null)
returns boolean language plpgsql security invoker set search_path=public as $$
begin
 update public.dufynd_external_observers set last_attempt_at=now(),consecutive_failures=consecutive_failures+1,
 health_status=case when p_error='missing_autonomous_credential' or p_status=401 then 'blocked_configuration'
 when p_error='gmail_history_expired' then 'resync_required' when consecutive_failures>=2 then 'stale' else 'degraded' end,
 next_retry_at=now()+make_interval(secs=>least(3600,greatest(120,coalesce(p_retry_seconds,(120*power(2,least(consecutive_failures,5)))::int)))),
 last_error=left(p_error,200),request_id=null,request_started_at=null where observer_id=p_observer_id;
 return found;
end $$;

create function public.normalize_dufynd_observation(p_type text,p_id text,p_raw jsonb,p_config jsonb default '{}')
returns jsonb language plpgsql immutable security invoker set search_path=public as $$
declare payload jsonb; state text; event text; x jsonb; m jsonb; result jsonb:='[]'; headers jsonb; bounce boolean;
begin
 if jsonb_typeof(p_raw) is null or length(p_raw::text)>1000000 then raise exception 'bounded response exceeded'; end if;
 if p_type='github_branch' then
  if p_raw->>'name' is distinct from p_id or coalesce(p_raw->'commit'->>'sha','') !~ '^[a-f0-9]{40}$' then raise exception 'branch identity mismatch'; end if;
  payload:=jsonb_build_object('sha',p_raw->'commit'->>'sha'); event:='github.branch.head_moved';
 elsif p_type='github_pr' then
  if p_raw->>'number' is distinct from p_id or p_raw->'base'->>'ref' is distinct from 'scentai-mvp' or coalesce(p_raw->'head'->>'sha','') !~ '^[a-f0-9]{40}$' or coalesce(p_raw->'base'->>'sha','') !~ '^[a-f0-9]{40}$' then raise exception 'PR identity mismatch'; end if;
  state:=case when p_raw->>'merged'='true' then 'merged' when p_raw->>'state'='closed' then 'closed' else 'open' end;
  payload:=jsonb_build_object('state',state,'sha',p_raw->'head'->>'sha','base_sha',p_raw->'base'->>'sha','updated_at',p_raw->>'updated_at'); event:='github.pr.'||state;
 elsif p_type in ('github_ci','github_workflow') then
  if p_raw->>'id' is distinct from p_id or p_raw->>'head_branch' is distinct from 'scentai-mvp' or coalesce(p_raw->>'head_sha','') !~ '^[a-f0-9]{40}$' then raise exception 'run identity mismatch'; end if;
  if p_type='github_ci' and p_raw->>'path' is distinct from '.github/workflows/ci.yml' then raise exception 'CI workflow mismatch'; end if;
  state:=case when p_raw->>'status'='completed' then case when p_raw->>'conclusion'='success' then 'success' else 'failure' end
   when p_raw->>'status'='in_progress' then 'in_progress' when p_raw->>'status' in ('queued','waiting','pending','requested') then 'queued' else null end;
  if state is null then raise exception 'unknown run state'; end if;
  payload:=jsonb_build_object('state',state,'sha',p_raw->>'head_sha','run_id',p_id,'attempt',p_raw->'run_attempt','conclusion',p_raw->>'conclusion');
  event:=case when p_type='github_ci' then 'github.ci.' else 'github.workflow.' end||state;
 elsif p_type='render' then
  if jsonb_typeof(p_raw) is distinct from 'array' or jsonb_array_length(p_raw)>20 then raise exception 'bounded deploy list required'; end if;
  for x in select value from jsonb_array_elements(p_raw) loop
   m:=coalesce(x->'deploy',x); state:=case when m->>'status'='live' then 'live'
    when m->>'status' in ('build_failed','update_failed','pre_deploy_failed','canceled') then 'failed'
    when m->>'status' in ('created','queued','build_in_progress','update_in_progress','pre_deploy_in_progress') then 'started' else null end;
   if state is not null and nullif(m->>'id','') is not null then
    result:=result||jsonb_build_array(jsonb_build_object('event_type','render.deployment.'||state,'cursor',(m->>'id')||':'||(m->>'status'),
    'payload',jsonb_build_object('state',state,'deployment_id',m->>'id','service_id',p_id,'sha',m->'commit'->>'id')));
   if state='live' and coalesce(m->'commit'->>'id','') ~ '^[a-f0-9]{40}$' then
     result:=result||jsonb_build_array(jsonb_build_object('event_type','render.service.commit','cursor',m->'commit'->>'id','payload',jsonb_build_object('service_id',p_id,'sha',m->'commit'->>'id')));
    end if;
   end if;
  end loop; return result;
 elsif p_type='gmail' then
  -- Native history response: only messageAdded from the explicitly registered thread.
  if coalesce(p_raw->>'historyId','') !~ '^[0-9]+$' then raise exception 'invalid Gmail history cursor'; end if;
  if not p_raw ? 'id' and not p_raw ? 'messages' and not p_raw ? 'history' then return '[]'; end if;
  if p_raw ? 'history' then
   if jsonb_typeof(p_raw->'history') is distinct from 'array' then raise exception 'invalid history'; end if;
   if jsonb_array_length(p_raw->'history')>100 then raise exception 'bounded Gmail history required'; end if;
   for x in select value from jsonb_array_elements(p_raw->'history') loop
    for m in select value->'message' from jsonb_array_elements(coalesce(x->'messagesAdded','[]')) loop
     if m->>'threadId'=p_id and not coalesce(m->'labelIds','[]') ? 'SENT' then
      result:=result||jsonb_build_array(jsonb_build_object('event_type','gmail.message.received','cursor',x->>'id','payload',jsonb_build_object('thread_id',p_id,'message_id',m->>'id','history_id',x->>'id')));
     end if;
    end loop;
   end loop; return result;
  end if;
  if p_raw->>'id' is distinct from p_id or jsonb_typeof(p_raw->'messages') is distinct from 'array' or jsonb_array_length(p_raw->'messages')>100 then raise exception 'known bounded Gmail thread required'; end if;
  for m in select value from jsonb_array_elements(p_raw->'messages') loop
   if coalesce(m->>'id','') !~ '^[a-f0-9]+$' or coalesce(m->>'internalDate','') !~ '^[0-9]+$' or m->>'threadId' is distinct from p_id then raise exception 'foreign message rejected'; end if;
   if coalesce(m->'labelIds','[]') ? 'SENT' or coalesce(m->'labelIds','[]') ? 'DRAFT' then continue; end if;
   headers:=coalesce(m->'payload'->'headers','[]');
   bounce:=exists(select 1 from jsonb_array_elements(headers) h where lower(h->>'name')='content-type' and lower(h->>'value') like '%delivery-status%')
    or exists(select 1 from jsonb_array_elements(headers) h where lower(h->>'name')='from' and lower(h->>'value') ~ '(mailer-daemon|postmaster)');
   result:=result||jsonb_build_array(jsonb_build_object('event_type',case when bounce then 'gmail.delivery_failure' else 'gmail.message.received' end,
    'cursor',p_raw->>'historyId','payload',jsonb_build_object('thread_id',p_id,'message_id',m->>'id','internal_date',m->>'internalDate','history_id',p_raw->>'historyId')));
  end loop; return result;
 elsif p_type='internal_dependency' then
  if p_raw->>'task_id' is distinct from p_id or p_raw->>'status' is distinct from 'done' then return '[]'; end if;
  payload:=jsonb_build_object('task_id',p_id,'state','done'); event:='internal.dependency.completed';
 else raise exception 'unknown source'; end if;
 return jsonb_build_array(jsonb_build_object('event_type',event,'cursor',coalesce(payload->>'updated_at',payload->>'sha',payload->>'state'),'payload',payload));
end $$;

create function public.capture_dufynd_observation(p_observer_id text,p_raw jsonb)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare o public.dufynd_external_observers; events jsonb; x jsonb; previous jsonb; fp text; related jsonb; eid uuid; inserted int:=0; msg text; observed_ids jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 select * into o from public.dufynd_external_observers where observer_id=p_observer_id for update;
 if not found or not o.enabled then return jsonb_build_object('accepted',false,'reason','unknown_observer'); end if;
 events:=public.normalize_dufynd_observation(o.source_type,o.source_id,p_raw,o.config);
 observed_ids:=coalesce(o.last_snapshot->'seen_message_ids','[]');
 for x in select value from jsonb_array_elements(events) loop
  if o.source_type='github_branch' and (o.last_snapshot='{}' or o.last_snapshot->>'sha'=x->'payload'->>'sha') then continue; end if;
  if o.source_type='github_pr' and x->'payload'=o.last_snapshot then continue; end if;
  if o.source_type='github_pr' and o.last_snapshot<>'{}' then
   if x->'payload'->>'state'='open' and o.last_snapshot->>'base_sha' is distinct from x->'payload'->>'base_sha' then x:=jsonb_set(x,'{event_type}','"github.pr.base_moved"');
   elsif x->'payload'->>'state'='open' then x:=jsonb_set(x,'{event_type}','"github.pr.updated"'); end if;
  end if;
  if o.source_type='gmail' then
   msg:=x->'payload'->>'message_id';
   if msg is null or observed_ids ? msg then continue; end if;
   -- Thread rebaseline cannot replay messages at/before its retained watermark.
   if x->'payload' ? 'internal_date' and coalesce(o.last_snapshot->>'watermark_ms','') ~ '^[0-9]+$'
    and (x->'payload'->>'internal_date')::numeric < (o.last_snapshot->>'watermark_ms')::numeric then continue; end if;
   observed_ids:=observed_ids||jsonb_build_array(msg);
  end if;
  fp:=encode(sha256(convert_to(jsonb_build_array(o.source_type,o.source_id,x->>'event_type',case when o.source_type='gmail' then jsonb_build_object('message_id',x->'payload'->>'message_id') else x->'payload' end)::text,'UTF8')),'hex');
  select coalesce(jsonb_agg(task_id),'[]') into related from public.dufynd_task_external_waits where observer_id=o.observer_id;
  insert into public.dufynd_jarvis_inbox(event_type,source_type,source_id,payload,status,source_cursor,fingerprint,related_task_ids)
   values(x->>'event_type',o.source_type,o.source_id,jsonb_build_object('observer_id',o.observer_id,'evidence',x->'payload'),'pending',x->>'cursor',fp,related)
   on conflict(fingerprint) where fingerprint is not null do nothing returning event_id into eid;
  if found then inserted:=inserted+1; end if;
 end loop;
 if o.source_type='gmail' then
  select coalesce(jsonb_agg(value order by ordinal),'[]') into observed_ids from jsonb_array_elements(observed_ids) with ordinality q(value,ordinal) where ordinal>greatest(0,jsonb_array_length(observed_ids)-500);
  previous:=jsonb_build_object('seen_message_ids',observed_ids,'watermark_ms',greatest((select max((m->>'internalDate')::numeric) from jsonb_array_elements(coalesce(p_raw->'messages','[]')) m),nullif(o.last_snapshot->>'watermark_ms','')::numeric)::text);
 elsif jsonb_array_length(events)>0 then previous:=events->0->'payload'; else previous:=o.last_snapshot; end if;
 update public.dufynd_external_observers set last_attempt_at=now(),last_success_at=now(),consecutive_failures=0,health_status='healthy',last_error=null,
  next_retry_at=now()+make_interval(secs=>interval_seconds),request_id=null,request_started_at=null,last_snapshot=previous,
  last_cursor=case when p_raw ? 'nextPageToken' then last_cursor when o.source_type='gmail' then greatest(nullif(last_cursor,'')::numeric,(p_raw->>'historyId')::numeric)::text else coalesce(events->0->>'cursor',last_cursor) end,
  page_token=p_raw->>'nextPageToken',last_event_at=case when inserted>0 then now() else last_event_at end where observer_id=o.observer_id;
 return jsonb_build_object('accepted',true,'inserted',inserted);
end $$;

create function public.bind_dufynd_external_wait(p_task_id text,p_observer_id text,p_event_types jsonb,p_expected_sha text default null,p_policy text default 'dependency')
returns boolean language plpgsql security invoker set search_path=public as $$
declare kind text;
begin
 select source_type into kind from public.dufynd_external_observers where observer_id=p_observer_id;
 if kind is null or p_policy is null or p_policy not in ('dependency','review','freshness') or jsonb_typeof(p_event_types) is distinct from 'array' or jsonb_array_length(p_event_types)=0 then return false; end if;
 if p_policy='dependency' and kind in ('github_ci','github_workflow','render') and coalesce(p_expected_sha,'') !~ '^[a-f0-9]{40}$' then return false; end if;
 if kind='gmail' and p_policy<>'review' then return false; end if;
 -- Failure observations never certify a dependency, even if misconfigured by a caller.
 if p_policy='dependency' and exists(select 1 from jsonb_array_elements_text(p_event_types) e where e ~ '(failure|failed|queued|in_progress|started|closed)$') then return false; end if;
 insert into public.dufynd_task_external_waits(task_id,observer_id,event_types,expected_sha,policy)
 values(p_task_id,p_observer_id,p_event_types,p_expected_sha,p_policy) on conflict(task_id,observer_id) do nothing;
 return true;
end $$;

create function public.process_dufynd_external_events() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare ev public.dufynd_jarvis_inbox; w record; t public.dufynd_autonomy_tasks; affected int:=0; processed int:=0; kind text; matched boolean; ready boolean; prepared jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 perform set_config('dufynd.event_processing','true',true);
 perform set_config('dufynd.worker_write','supervisor',true);
 for ev in select * from public.dufynd_jarvis_inbox where fingerprint is not null and status='pending' order by inbox_id limit 100 for update skip locked loop
  for w in select * from public.dufynd_task_external_waits where observer_id=ev.payload->>'observer_id' loop
   select * into t from public.dufynd_autonomy_tasks where task_id=w.task_id for update;
   if t.status='done' or t.status='in_progress' or exists(select 1 from public.dufynd_execution_runs where task_id=t.task_id and status not in ('completed','failed_terminal')) then continue; end if;
   kind:=ev.event_type; matched:=w.event_types ? kind and (w.expected_sha is null or w.expected_sha=ev.payload->'evidence'->>'sha');
   if matched then
    update public.dufynd_task_external_waits set satisfied=true,last_event_id=ev.event_id,reevaluated_at=now() where task_id=w.task_id and observer_id=w.observer_id;
    if w.policy='review' then
     update public.dufynd_autonomy_tasks set external_review_required=true,blocked_reason='external_response_review',
      status=case when requires_human_approval then status else 'ready' end,worker_state=case when requires_human_approval then worker_state else 'queued' end,
      evidence=right(coalesce(evidence,'')||E'\nObserved reply/delivery event; review required; no rights or publication approval inferred. Event '||ev.event_id::text,12000) where task_id=t.task_id;
    elsif w.policy='freshness' then
     update public.dufynd_task_external_waits set satisfied=false where task_id=t.task_id and policy='dependency';
     update public.dufynd_autonomy_tasks set needs_freshness_recheck=true,blocked_reason='freshness_recheck',status='waiting_external',worker_state='waiting_external' where task_id=t.task_id and not requires_human_approval;
    end if;
   elsif kind in ('github.ci.failure','github.workflow.failure','render.deployment.failed') and (w.expected_sha is null or w.expected_sha=ev.payload->'evidence'->>'sha') then
    update public.dufynd_task_external_waits set satisfied=false,last_event_id=ev.event_id,reevaluated_at=now() where task_id=w.task_id and observer_id=w.observer_id;
    update public.dufynd_autonomy_tasks set blocked_reason='external_failure_retryable',worker_state='failed_retryable',status='waiting_external' where task_id=t.task_id and not requires_human_approval;
   end if;
   update public.dufynd_autonomy_tasks set last_external_event_id=ev.event_id,evidence=right(coalesce(evidence,'')||E'\nExternal event '||ev.event_id::text||' '||ev.event_type,12000) where task_id=t.task_id;
   affected:=affected+1;
  end loop;
  if ev.source_type='internal_dependency' then
   update public.dufynd_autonomy_tasks set last_external_event_id=ev.event_id where dependencies ? ev.source_id and status in ('waiting_external','blocked')
    and not exists(select 1 from public.dufynd_execution_runs where task_id=dufynd_autonomy_tasks.task_id and status not in ('completed','failed_terminal'));
  end if;
  update public.dufynd_jarvis_inbox set status='done',processed_at=now(),attempts=attempts+1 where inbox_id=ev.inbox_id; processed:=processed+1;
 end loop;
 -- Only registered waiters with all external AND exact internal dependencies satisfied.
 for t in select * from public.dufynd_autonomy_tasks q where q.status in ('waiting_external','blocked','ready')
  and not q.requires_human_approval and not q.external_review_required and not q.needs_freshness_recheck
  and (exists(select 1 from public.dufynd_task_external_waits where task_id=q.task_id) or (jsonb_typeof(q.dependencies)='array' and jsonb_array_length(q.dependencies)>0))
  and not exists(select 1 from public.dufynd_task_external_waits where task_id=q.task_id and (not satisfied or policy<>'dependency'))
  and jsonb_typeof(q.dependencies)='array' and not exists(select 1 from jsonb_array_elements_text(q.dependencies) d where not exists(select 1 from public.dufynd_autonomy_tasks x where x.task_id=d and x.status='done'))
  and not exists(select 1 from public.dufynd_execution_runs where task_id=q.task_id and status not in ('completed','failed_terminal')) for update loop
  update public.dufynd_autonomy_tasks set status='ready',worker_state='ready',blocked_reason=null,evidence=right(coalesce(evidence,'')||E'\nDeterministic dependency reevaluation: ready.',12000) where task_id=t.task_id and (status<>'ready' or worker_state<>'ready' or blocked_reason is not null);
  -- No improvised handler, no paid fallback. Existing registry validates payload.
  if t.budget_class='free' and t.durable_payload is not null and t.durability_policy='durable' then
   prepared:=public.prepare_dufynd_execution(t.task_id,'event-wake:'||t.task_id,t.domain,t.resource_scope,t.durable_payload,'durable');
   -- prepare RPC resets its token context; restore for subsequent task/event writes.
   perform set_config('dufynd.worker_write','supervisor',true);
  end if;
 end loop;
 perform set_config('dufynd.worker_write','',true);
 perform set_config('dufynd.event_processing','',true);
 return jsonb_build_object('processed',processed,'affected',affected);
end $$;

-- Internal events arrive synchronously; only relevant dependencies are captured.
create function public.emit_dufynd_dependency_event() returns trigger
language plpgsql security invoker set search_path=public as $$
declare oid text:='internal_dependency:'||new.task_id; fp text;
begin
 if new.status='done' and old.status is distinct from new.status
 and exists(select 1 from public.dufynd_autonomy_tasks where dependencies ? new.task_id and status in ('waiting_external','blocked')) then
  insert into public.dufynd_external_observers(observer_id,source_type,source_id,health_status,last_success_at,last_cursor)
   values(oid,'internal_dependency',new.task_id,'healthy',now(),'done') on conflict(observer_id) do nothing;
  fp:=encode(sha256(convert_to(oid||':done','UTF8')),'hex');
  insert into public.dufynd_jarvis_inbox(event_type,source_type,source_id,payload,fingerprint,source_cursor,related_task_ids)
   select 'internal.dependency.completed','internal_dependency',new.task_id,jsonb_build_object('observer_id',oid,'evidence',jsonb_build_object('task_id',new.task_id,'state','done')),fp,'done',coalesce(jsonb_agg(task_id),'[]')
   from public.dufynd_autonomy_tasks where dependencies ? new.task_id and status in ('waiting_external','blocked')
   on conflict(fingerprint) where fingerprint is not null do nothing;
 end if; return new;
end $$;
create trigger dufynd_dependency_event after update of status on public.dufynd_autonomy_tasks for each row execute function public.emit_dufynd_dependency_event();

create function public.guard_dufynd_external_execution() returns trigger
language plpgsql security invoker set search_path=public as $$
begin
 if exists(select 1 from public.dufynd_autonomy_tasks t where t.task_id=new.task_id and
   (t.external_review_required or t.needs_freshness_recheck))
 or exists(select 1 from public.dufynd_task_external_waits where task_id=new.task_id and (not satisfied or policy<>'dependency')) then
  raise exception 'external dependency/review gate not certified';
 end if; return new;
end $$;
create trigger dufynd_external_execution_gate before insert on public.dufynd_execution_runs for each row execute function public.guard_dufynd_external_execution();

-- Keep external deterministic events away from the legacy SDK inbox consumer.
create or replace function public.claim_dufynd_jarvis_event() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare v public.dufynd_jarvis_inbox;
begin
 select * into v from public.dufynd_jarvis_inbox where status='pending' and fingerprint is null and available_at<=now() order by available_at,inbox_id for update skip locked limit 1;
 if not found then return null; end if;
 update public.dufynd_jarvis_inbox set status='processing',claimed_at=now(),attempts=attempts+1,updated_at=now() where inbox_id=v.inbox_id returning * into v;
 return to_jsonb(v);
end $$;

alter table public.dufynd_external_observers add column request_kind text,
 add column pending_cursor text,add column pending_page_token text;

create function public.poll_dufynd_observers() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare o public.dufynd_external_observers; r record; body jsonb; url text; headers jsonb; credential text; rid bigint; result jsonb; attempted int:=0; retry int; events jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 update public.dufynd_external_observers set health_status='stale',last_error='observer_success_stale'
 where enabled and source_type<>'internal_dependency' and health_status in ('healthy','degraded') and coalesce(last_success_at,last_attempt_at,'-infinity')<now()-make_interval(secs=>greatest(600,interval_seconds*3));
 if to_regnamespace('net') is null then return jsonb_build_object('available',false); end if;
 for o in select * from public.dufynd_external_observers where request_id is not null for update loop
  execute 'select status_code,content,headers,timed_out,error_msg from net._http_response where id=$1' into r using o.request_id;
  if r.status_code is null and o.request_started_at>now()-interval '60 seconds' then continue; end if;
  if r.status_code=304 then
   update public.dufynd_external_observers set last_success_at=now(),health_status='healthy',consecutive_failures=0,last_error=null,request_id=null,request_started_at=null,next_retry_at=now()+make_interval(secs=>interval_seconds) where observer_id=o.observer_id;
   continue;
  end if;
  if r.status_code is distinct from 200 then
   retry:=case when coalesce(r.headers->>'retry-after','') ~ '^[0-9]{1,5}$' then least(3600,(r.headers->>'retry-after')::int) else null end;
   perform public.dufynd_observer_failure(o.observer_id,case when r.status_code=404 and o.source_type='gmail' then 'gmail_history_expired'
    when r.status_code=429 or (r.status_code=403 and r.headers->>'x-ratelimit-remaining'='0') then 'rate_limited' else 'external_transport_failure' end,coalesce(r.status_code,0),retry);
   continue;
  end if;
  begin
   body:=r.content::jsonb;
   if o.source_type='gmail' and o.request_kind='history' then
    events:=public.normalize_dufynd_observation(o.source_type,o.source_id,body,o.config);
    if jsonb_array_length(events)>0 then
     update public.dufynd_external_observers set pending_cursor=body->>'historyId',pending_page_token=body->>'nextPageToken',request_id=null,request_kind='thread',next_retry_at=now() where observer_id=o.observer_id;
     continue; -- Known thread metadata on next request, never whole mailbox content.
    end if;
   end if;
   result:=public.capture_dufynd_observation(o.observer_id,body);
   if o.source_type='gmail' and o.request_kind='thread' and o.pending_cursor is not null then
    update public.dufynd_external_observers set last_cursor=case when o.pending_page_token is not null then o.last_cursor else o.pending_cursor end,
      page_token=o.pending_page_token,pending_cursor=null,pending_page_token=null,request_kind=null where observer_id=o.observer_id;
   end if;
   update public.dufynd_external_observers set etag=coalesce(r.headers->>'etag',r.headers->>'ETag',etag) where observer_id=o.observer_id;
  exception when others then perform public.dufynd_observer_failure(o.observer_id,'invalid_bounded_source_response'); end;
 end loop;
 -- Missing credentials are visible unhealthy configuration, not invented success.
 for o in select * from public.dufynd_external_observers where enabled and source_type in ('render','gmail') and request_id is null and next_retry_at<=now() loop
  credential:=null;
  if to_regclass('vault.decrypted_secrets') is not null then
   begin
   execute 'select decrypted_secret from vault.decrypted_secrets where name=$1 limit 1' into credential
    using case when o.source_type='render' then 'dufynd_observer_render_read_token' else 'dufynd_observer_gmail_read_access_token' end;
   exception when insufficient_privilege then credential:=null; end;
  end if;
  if credential is null then perform public.dufynd_observer_failure(o.observer_id,'missing_autonomous_credential',0,900); end if;
 end loop;
 select * into o from public.dufynd_external_observers where enabled and source_type<>'internal_dependency'
  and request_id is null and next_retry_at<=now() order by next_retry_at,last_attempt_at nulls first limit 1 for update;
 if not found then return jsonb_build_object('attempted',0); end if;
 headers:='{"Accept":"application/json","User-Agent":"DUFYND-Supervisor-V2","X-GitHub-Api-Version":"2022-11-28"}';
 if o.etag is not null then headers:=headers||jsonb_build_object('If-None-Match',o.etag); end if;
 if o.source_type='github_branch' then url:='https://api.github.com/repos/tncommerce/commerce-agents/branches/scentai-mvp';
 elsif o.source_type='github_pr' then url:='https://api.github.com/repos/tncommerce/commerce-agents/pulls/'||o.source_id;
 elsif o.source_type in ('github_ci','github_workflow') then url:='https://api.github.com/repos/tncommerce/commerce-agents/actions/runs/'||o.source_id;
 elsif o.source_type in ('render','gmail') then
  execute 'select decrypted_secret from vault.decrypted_secrets where name=$1 limit 1' into credential
   using case when o.source_type='render' then 'dufynd_observer_render_read_token' else 'dufynd_observer_gmail_read_access_token' end;
  if credential is null then return jsonb_build_object('attempted',0); end if;
  headers:=headers||jsonb_build_object('Authorization','Bearer '||credential);
  if o.source_type='render' then url:='https://api.render.com/v1/services/'||o.source_id||'/deploys?limit=20';
  elsif o.pending_cursor is not null or o.last_cursor is null or o.health_status='resync_required' then
   url:='https://gmail.googleapis.com/gmail/v1/users/me/threads/'||o.source_id||'?format=metadata&metadataHeaders=From&metadataHeaders=Content-Type';
   update public.dufynd_external_observers set request_kind='thread' where observer_id=o.observer_id;
  else
   url:='https://gmail.googleapis.com/gmail/v1/users/me/history?startHistoryId='||o.last_cursor||'&historyTypes=messageAdded&maxResults=100';
   if o.page_token is not null then url:=url||'&pageToken='||replace(replace(replace(o.page_token,'+','%2B'),'/','%2F'),'=','%3D'); end if;
   update public.dufynd_external_observers set request_kind='history' where observer_id=o.observer_id;
  end if;
 else return jsonb_build_object('attempted',0); end if;
 execute 'select net.http_get(url:=$1,headers:=$2,timeout_milliseconds:=5000)' into rid using url,headers;
 update public.dufynd_external_observers set request_id=rid,request_started_at=now(),last_attempt_at=now() where observer_id=o.observer_id;
 return jsonb_build_object('attempted',1);
end $$;

create function public.get_dufynd_observer_health() returns jsonb
language sql stable security invoker set search_path=public as $$
select coalesce(jsonb_agg(jsonb_build_object('observer_id',observer_id,'source_type',source_type,'enabled',enabled,
 'last_attempt_at',last_attempt_at,'last_success_at',last_success_at,'last_cursor',last_cursor,'last_event_at',last_event_at,
 'consecutive_failures',consecutive_failures,'next_retry_at',next_retry_at,'last_error',last_error,
 'health_status',case when enabled and source_type<>'internal_dependency' and health_status in ('healthy','degraded') and coalesce(last_success_at,last_attempt_at,'-infinity')<now()-make_interval(secs=>greatest(600,interval_seconds*3)) then 'stale' else health_status end)),'[]') from public.dufynd_external_observers;
$$;

create function public.has_dufynd_durable_event_waiters() returns boolean
language sql stable security invoker set search_path=public as $$
select exists(select 1 from public.dufynd_autonomy_tasks t where t.budget_class='free' and t.durability_policy='durable'
 and t.durable_payload->>'kind'='durability_probe' and not t.requires_human_approval and not t.external_review_required and not t.needs_freshness_recheck
 and t.status in ('waiting_external','ready') and not exists(select 1 from public.dufynd_execution_runs where task_id=t.task_id));
$$;

alter function public.reconcile_dufynd_supervisor_v2() rename to reconcile_dufynd_supervisor_v2_phase2b;
create function public.reconcile_dufynd_supervisor_v2() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare observers jsonb; events jsonb; prior jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 -- claim_worker calls the supervisor: avoid recursive event -> prepare -> claim -> event.
 if current_setting('dufynd.event_processing',true)='true' then return public.reconcile_dufynd_supervisor_v2_phase2b(); end if;
 observers:=public.poll_dufynd_observers();
 events:=public.process_dufynd_external_events();
 prior:=public.reconcile_dufynd_supervisor_v2_phase2b();
 update public.dufynd_master_status set value=value||jsonb_build_object('observer_health',public.get_dufynd_observer_health(),'external_events',events,'observer_poll',observers) where key='jarvis.supervisor_v2.health';
 return prior||jsonb_build_object('observer_health',public.get_dufynd_observer_health(),'external_events',events);
end $$;

do $$ declare f record; begin
 for f in select oid::regprocedure as signature from pg_proc where pronamespace='public'::regnamespace
 and proname in ('guard_dufynd_external_execution','register_dufynd_observer','dufynd_observer_failure','normalize_dufynd_observation','capture_dufynd_observation','bind_dufynd_external_wait','process_dufynd_external_events','emit_dufynd_dependency_event','claim_dufynd_jarvis_event','poll_dufynd_observers','get_dufynd_observer_health','has_dufynd_durable_event_waiters','reconcile_dufynd_supervisor_v2','reconcile_dufynd_supervisor_v2_phase2b') loop
  execute 'revoke all on function '||f.signature||' from public,anon,authenticated';
  execute 'grant execute on function '||f.signature||' to service_role';
 end loop;
end $$;
