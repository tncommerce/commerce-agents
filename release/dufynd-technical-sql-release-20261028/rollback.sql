-- Controlled rollback: refuses unknown later definitions or changed ACLs.
-- Supports rollback after either one or both technical migrations.
begin;
set local lock_timeout='5s';
set local statement_timeout='30s';
select pg_advisory_xact_lock(hashtext('dufynd-free-planner-v1'));
select pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
do $rollback_guard$
declare r record;
begin
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.plan_dufynd_free_work_v1()');
 if r.definition_md5 is null or r.definition_md5 not in ('048fa0a0c4f114e641fd97463848dc5c','0fb393ff9dcd50376772556c73a6d07d')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 'v' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.plan_dufynd_free_work_v1()';
 end if;
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.poll_dufynd_observers()');
 if r.definition_md5 is null or r.definition_md5 not in ('fdbb921ba914178935e81b2d2e3bde8e','b16099ccc4633cafb48dcb81044738ad')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 'v' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.poll_dufynd_observers()';
 end if;
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.read_dufynd_safe_work_exhaustion_v1()');
 if r.definition_md5 is null or r.definition_md5 not in ('df57cc1746168a917c2d0a6bfe14bc07','9b85321f0afb551ceb44700ab458eff7')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 's' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.read_dufynd_safe_work_exhaustion_v1()';
 end if;
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.read_dufynd_technical_work_blockers_v1()');
 if r.definition_md5 is null then null; elsif r.definition_md5 is null or r.definition_md5 not in ('0f9e888aa4d1f853d8a0fc0e9c84cb9b')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 's' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.read_dufynd_technical_work_blockers_v1()';
 end if;
end;
$rollback_guard$;
CREATE OR REPLACE FUNCTION public.plan_dufynd_free_work_v1()
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
declare
  before_state jsonb;
  after_state jsonb;
  wake_result jsonb;
  affiliate_plan jsonb;
  content_plan jsonb;
  packet_plan jsonb;
  measurement_plan jsonb;
  business_plan jsonb;
  exhaustion jsonb;
  report jsonb;
  external_evidence text;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-free-planner-v1'));
  before_state := public.get_dufynd_next_autonomous_action();

  if before_state->>'state' in ('work_available','work_in_progress','owner_gate') then
    report := jsonb_build_object(
      'version',6,'observed_at',now(),'state',before_state->>'state',
      'action','none','reason','existing_work_or_gate_already_explains_next_step',
      'queue',before_state,'new_spend_usd',0
    );
  else
    -- Existing deterministic plans only. No new task type, scheduler or
    -- external execution is added by this patch.
    wake_result := public.wake_dufynd_purchase_freshness();
    after_state := public.get_dufynd_next_autonomous_action();

    if after_state->>'state'='work_available' then
      report := jsonb_build_object(
        'version',6,'observed_at',now(),'state','work_replenished',
        'action','purchase_freshness_wake','wake_result',wake_result,
        'queue',after_state,'new_spend_usd',0
      );
    else
      affiliate_plan := public.plan_dufynd_affiliate_work_v1();
      after_state := public.get_dufynd_next_autonomous_action();

      if after_state->>'state'='work_available' then
        report := jsonb_build_object(
          'version',6,'observed_at',now(),'state','work_replenished',
          'action','affiliate_evidence_planning','affiliate_plan',affiliate_plan,
          'queue',after_state,'new_spend_usd',0
        );
      else
        content_plan := public.plan_dufynd_zero_budget_content_work_v1();
        after_state := public.get_dufynd_next_autonomous_action();

        if after_state->>'state'='work_available' then
          report := jsonb_build_object(
            'version',6,'observed_at',now(),'state','work_replenished',
            'action','zero_budget_content_planning','content_plan',content_plan,
            'queue',after_state,'new_spend_usd',0
          );
        else
          packet_plan := public.plan_dufynd_content_packet_work_v1();
          after_state := public.get_dufynd_next_autonomous_action();

          if after_state->>'state'='work_available' then
            report := jsonb_build_object(
              'version',6,'observed_at',now(),'state','work_replenished',
              'action','content_packet_planning','content_plan',content_plan,
              'packet_plan',packet_plan,'queue',after_state,'new_spend_usd',0
            );
          else
            measurement_plan := public.plan_dufynd_measurement_work_v1();
            after_state := public.get_dufynd_next_autonomous_action();

            if after_state->>'state'='work_available' then
              report := jsonb_build_object(
                'version',6,'observed_at',now(),'state','work_replenished',
                'action','first_money_measurement_planning',
                'measurement_plan',measurement_plan,'queue',after_state,'new_spend_usd',0
              );
            else
              business_plan := public.plan_dufynd_autonomous_business_work_v1();
              after_state := public.get_dufynd_next_autonomous_action();
              exhaustion := public.read_dufynd_safe_work_exhaustion_v1();

              if coalesce((exhaustion->>'safe_internal_work_exhausted')::boolean,false) then
                external_evidence := exhaustion->>'next_external_evidence';
                report := jsonb_build_object(
                  'version',6,'observed_at',now(),'state','waiting_market_signal',
                  'action',case external_evidence
                    when 'qualified_session' then 'wait_for_qualified_distribution_signal'
                    when 'merchant_clickout' then 'wait_for_verified_merchant_clickout'
                    when 'affiliate_transaction_evidence' then 'wait_for_original_network_transaction'
                  end,
                  'reason','no_certified_safe_work_currently_executable',
                  'next_external_evidence',external_evidence,
                  'blocked_transport_count',exhaustion->'blocked_transport_count',
                  'measurement_plan',measurement_plan,
                  'exhaustion',exhaustion,'queue',after_state,
                  'master_action_required',false,'new_spend_usd',0
                );
              else
                report := jsonb_build_object(
                  'version',6,'observed_at',now(),
                  'state',case
                    when after_state->>'state'='work_available' then 'work_replenished'
                    when after_state->>'state'='work_in_progress' then 'work_in_progress'
                    when after_state->>'state'='owner_gate' then 'owner_gate'
                    else coalesce(business_plan->>'state','planner_gap')
                  end,
                  'action','autonomous_business_planning','wake_result',wake_result,
                  'affiliate_plan',affiliate_plan,'content_plan',content_plan,
                  'packet_plan',packet_plan,
                  'measurement_plan',measurement_plan,'business_plan',business_plan,
                  'exhaustion',exhaustion,'queue',after_state,
                  'business_next_move',business_plan->>'business_next_move',
                  'master_action_required',false,
                  'waiting_external_is_global_blocker',false,'new_spend_usd',0
                );
              end if;
            end if;
          end if;
        end if;
      end if;
    end if;
  end if;

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.planner_v1','jarvis',report,100,now())
  on conflict(key) do update
  set value=excluded.value,priority=excluded.priority,last_verified_at=excluded.last_verified_at;

  return report;
end;
$function$;
CREATE OR REPLACE FUNCTION public.poll_dufynd_observers()
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
declare o public.dufynd_external_observers; r record; body jsonb; url text; headers jsonb; credential_health jsonb; rid bigint; result jsonb; attempted int:=0; retry int; events jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 update public.dufynd_external_observers set health_status='stale',last_error='observer_success_stale'
 where enabled and source_type in ('github_branch','github_pr','github_ci','github_workflow') and health_status in ('healthy','degraded') and coalesce(last_success_at,last_attempt_at,'-infinity')<now()-make_interval(secs=>greatest(600,interval_seconds*3));
 if to_regnamespace('net') is null then return jsonb_build_object('available',false); end if;
 for o in select * from public.dufynd_external_observers where request_id is not null and source_type not in ('render','gmail') for update loop
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
 -- External providers are private-broker only, never a broad Vault key read.
 for o in select * from public.dufynd_external_observers where enabled and source_type in ('render','gmail') loop
  update public.dufynd_external_observers set request_id=null,request_started_at=null where observer_id=o.observer_id;
  credential_health:=public.get_dufynd_credential_health(o.source_type);
  if not coalesce((credential_health->>'activation_enabled')::boolean,false)
   or credential_health->>'status' not in ('healthy','expiring') then
   update public.dufynd_external_observers set health_status='blocked_configuration',
    last_error=case when credential_health->>'status' in ('healthy','expiring') then 'broker_activation_required' else 'credential_'||(credential_health->>'status') end,
    request_id=null,request_started_at=null where observer_id=o.observer_id;
  end if;
 end loop;
 select * into o from public.dufynd_external_observers where enabled and source_type in ('github_branch','github_pr','github_ci','github_workflow')
  and request_id is null and next_retry_at<=now() order by next_retry_at,last_attempt_at nulls first limit 1 for update;
 if not found then return jsonb_build_object('attempted',0); end if;
 headers:='{"Accept":"application/json","User-Agent":"DUFYND-Supervisor-V2","X-GitHub-Api-Version":"2022-11-28"}';
 if o.etag is not null then headers:=headers||jsonb_build_object('If-None-Match',o.etag); end if;
 if o.source_type='github_branch' then url:='https://api.github.com/repos/tncommerce/commerce-agents/branches/scentai-mvp';
 elsif o.source_type='github_pr' then url:='https://api.github.com/repos/tncommerce/commerce-agents/pulls/'||o.source_id;
 elsif o.source_type in ('github_ci','github_workflow') then url:='https://api.github.com/repos/tncommerce/commerce-agents/actions/runs/'||o.source_id;
 else return jsonb_build_object('attempted',0); end if;
 execute 'select net.http_get(url:=$1,headers:=$2,timeout_milliseconds:=5000)' into rid using url,headers;
 update public.dufynd_external_observers set request_id=rid,request_started_at=now(),last_attempt_at=now() where observer_id=o.observer_id;
 return jsonb_build_object('attempted',1);
end $function$;
CREATE OR REPLACE FUNCTION public.read_dufynd_safe_work_exhaustion_v1()
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE
 SET search_path TO 'public'
AS $function$
declare
  fm jsonb;
  m jsonb;
  queue_state jsonb;
  day_key text := to_char(now() at time zone 'UTC','YYYYMMDD');
  content_queue_done boolean;
  content_packet_done boolean;
  content_reuse_done boolean;
  measurement_done boolean;
  measurement_work_due boolean;
  measurement_gate_satisfied boolean;
  next_external_evidence text;
  executable_count integer;
  owner_gate_count integer;
  blocked_transport_count integer;
  exhausted boolean;
  reason text;
begin
  fm := public.read_dufynd_first_money_runtime();
  m := public.read_dufynd_first_money_measurement_audit_v1();

  select exists(
    select 1 from public.dufynd_autonomy_tasks
    where task_id='bizplan:zero-budget-content-queue:'||day_key and status='done'
  ) into content_queue_done;

  select exists(
    select 1 from public.dufynd_autonomy_tasks
    where task_id like 'bizplan:content-packet:%:'||day_key and status='done'
  ) into content_packet_done;

  select exists(
    select 1 from public.dufynd_autonomy_tasks
    where task_id='bizplan:creative-recovery:'||day_key and status='done'
  ) into content_reuse_done;

  select exists(
    select 1 from public.dufynd_autonomy_tasks
    where task_id='bizplan:first-money-measurement:'||day_key and status='done'
  ) into measurement_done;

  -- Reuse the actual queue's lease/approval classification. A task with an
  -- active lease or a human gate is NOT a completed/no-work condition.
  queue_state := public.get_dufynd_next_autonomous_action();
  executable_count := coalesce((queue_state->>'ready_count')::integer,0)
                    + coalesce((queue_state->>'active_count')::integer,0);
  owner_gate_count := coalesce((queue_state->>'waiting_human_count')::integer,0)
                    + coalesce((queue_state->>'approval_count')::integer,0);

  -- Report real technical dead letters separately. A blocked task is not a
  -- safe runnable task and must not be revived merely to fill the queue.
  select count(*)::integer into blocked_transport_count
  from public.dufynd_autonomy_tasks
  where status='blocked' and blocked_reason='transport_unverified';

  -- Require exact alignment between the first-party next-evidence marker and
  -- the independent measurement audit. Unknown or conflicting evidence fails
  -- closed; a clickout is never a sale and never a proven network commission.
  next_external_evidence := case
    when fm->>'next_evidence'='qualified_session'
     and m->>'decision'='waiting_for_qualified_distribution_signal'
      then 'qualified_session'
    when fm->>'next_evidence'='merchant_clickout'
     and m->>'decision'='qualified_traffic_present_no_clickout'
      then 'merchant_clickout'
    when fm->>'next_evidence'='affiliate_transaction_evidence'
     and m->>'decision'='attributed_clickout_signal_present'
      then 'affiliate_transaction_evidence'
    else null
  end;

  -- Existing plan_dufynd_measurement_work_v1 creates a daily diagnostic only
  -- for next_evidence='qualified_session'. Keep measurement_done as the REAL
  -- completion flag; report separately that later stages have no task due.
  measurement_work_due := fm->>'next_evidence'='qualified_session';
  measurement_gate_satisfied := case
    when next_external_evidence='qualified_session' then measurement_done
    when next_external_evidence in ('merchant_clickout','affiliate_transaction_evidence')
      then true
    else false
  end;

  exhausted :=
    queue_state->>'state'='planner_gap'
    and executable_count=0
    and owner_gate_count=0
    and content_queue_done
    and content_packet_done
    and content_reuse_done
    and measurement_gate_satisfied
    and next_external_evidence is not null;

  reason := case
    when exhausted and next_external_evidence='qualified_session'
      then 'qualified_distribution_signal_required'
    when exhausted and next_external_evidence='merchant_clickout'
      then 'merchant_clickout_signal_required'
    when exhausted and next_external_evidence='affiliate_transaction_evidence'
      then 'original_network_transaction_evidence_required'
    when queue_state->>'state'='work_available' then 'certified_work_available'
    when queue_state->>'state'='work_in_progress' then 'certified_work_in_progress'
    when queue_state->>'state'='owner_gate' then 'owner_approval_required'
    when next_external_evidence is null then 'first_money_evidence_unverified_or_missing'
    else 'internal_work_or_gate_remains'
  end;

  return jsonb_build_object(
    'version',1,'observed_at',now(),
    'safe_internal_work_exhausted',exhausted,
    'content_queue_done',content_queue_done,
    'content_packet_done',content_packet_done,
    'content_reuse_done',content_reuse_done,
    'measurement_done',measurement_done,
    'measurement_work_due',measurement_work_due,
    'measurement_gate_satisfied',measurement_gate_satisfied,
    'executable_count',executable_count,
    'owner_gate_count',owner_gate_count,
    'queue_state',queue_state->>'state',
    'blocked_transport_count',blocked_transport_count,
    'next_external_evidence',next_external_evidence,
    'first_money_next_evidence',fm->>'next_evidence',
    'measurement_decision',m->>'decision',
    'reason',reason,'new_spend_usd',0
  );
end;
$function$;
drop function if exists public.read_dufynd_technical_work_blockers_v1();
do $rollback_postcondition$
declare r record;
begin
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.plan_dufynd_free_work_v1()');
 if r.definition_md5 is null or r.definition_md5 not in ('0fb393ff9dcd50376772556c73a6d07d')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 'v' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.plan_dufynd_free_work_v1()';
 end if;
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.poll_dufynd_observers()');
 if r.definition_md5 is null or r.definition_md5 not in ('b16099ccc4633cafb48dcb81044738ad')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 'v' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.poll_dufynd_observers()';
 end if;
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.read_dufynd_safe_work_exhaustion_v1()');
 if r.definition_md5 is null or r.definition_md5 not in ('9b85321f0afb551ceb44700ab458eff7')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 's' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.read_dufynd_safe_work_exhaustion_v1()';
 end if;
 if to_regprocedure('public.read_dufynd_technical_work_blockers_v1()') is not null then
  raise exception 'DUFYND release requires absent helper: public.read_dufynd_technical_work_blockers_v1()';
 end if;
end;
$rollback_postcondition$;
commit;
