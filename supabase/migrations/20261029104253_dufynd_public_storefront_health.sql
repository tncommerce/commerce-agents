-- Independent public HTML liveness using the existing observer cron/pg_net.
-- No JS, analytics, merchant clickout, credential, deployment or business proof.
-- pg_net follows redirects: the fixed initial URL is trusted, but the final
-- origin/redirect chain is not attested. Reject visible redirects/Location.
INSERT INTO public.dufynd_master_status(key,category,value,priority,last_verified_at)
VALUES ('ops.public_storefront_health_v1','operations',jsonb_build_object(
  'version',1,'enabled',false,'status','disabled','config_checked_at',clock_timestamp(),
  'endpoint','https://dufynd.de/','canonical','https://dufynd.de',
  'scope','public_storefront_liveness_only','interval_seconds',120,'freshness_seconds',600,
  'private_observer_evidence',false,'full_chain_complete',false,
  'deployment_revision_verified',false,'redirect_chain_verified',false,'final_origin_verified',false
),90,clock_timestamp()) ON CONFLICT(key) DO NOTHING;

CREATE OR REPLACE FUNCTION public.read_dufynd_public_storefront_health_v1()
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path TO pg_catalog,public
AS $storefront_read$
DECLARE
 s jsonb; result jsonb; success_at timestamptz; valid_until timestamptz;
 requested_at timestamptz; observed_at timestamptz; status text; response_bytes integer;
BEGIN
 SELECT value INTO s FROM public.dufynd_master_status WHERE key='ops.public_storefront_health_v1';
 observed_at:=clock_timestamp();
 IF jsonb_typeof(s) IS DISTINCT FROM 'object' THEN s:='{}'::jsonb; END IF;
 result:=jsonb_build_object(
   'version',1,'enabled',s->'enabled'='true'::jsonb,
   'endpoint','https://dufynd.de/','canonical','https://dufynd.de',
   'scope','public_storefront_liveness_only','private_observer_evidence',false,
   'full_chain_complete',false,'deployment_revision_verified',false,
   'redirect_chain_verified',false,'final_origin_verified',false,
   'redirect_behavior','pg_net_follows_redirects','javascript_executed',false,
   'healthy',false,'observed_at',observed_at,'interval_seconds',120,'freshness_seconds',600,
   'last_success_at',s->'last_success_at','valid_until',s->'valid_until',
   'last_attempt_at',s->'last_attempt_at','next_poll_at',s->'next_poll_at',
   'last_error',s->'last_error','last_status_code',s->'last_status_code',
   'last_response_bytes',s->'last_response_bytes','html_contract',s->'html_contract',
   'consecutive_failures',s->'consecutive_failures','request_pending',s ? 'request_id'
 );
 IF s->'enabled' IS DISTINCT FROM 'true'::jsonb THEN
   RETURN result||jsonb_build_object('status','disabled','enabled',false);
 END IF;
 BEGIN success_at:=(s->>'last_success_at')::timestamptz;
 EXCEPTION WHEN OTHERS THEN success_at:=null; END;
 BEGIN valid_until:=(s->>'valid_until')::timestamptz;
 EXCEPTION WHEN OTHERS THEN valid_until:=null; END;
 BEGIN requested_at:=(s->>'requested_at')::timestamptz;
 EXCEPTION WHEN OTHERS THEN requested_at:=null; END;
 IF jsonb_typeof(s->'last_response_bytes')='number'
    AND coalesce(s->>'last_response_bytes','') ~ '^[0-9]{1,6}$' THEN
   response_bytes:=(s->>'last_response_bytes')::integer;
 END IF;
 -- Preserve a recent successful receipt during one normal consumer cadence;
 -- an overdue/invalid pending identity cannot hide behind that old success.
 IF s ? 'request_id' AND (coalesce(s->>'request_id','') !~ '^[1-9][0-9]{0,17}$'
    OR requested_at IS NULL OR NOT isfinite(requested_at)
    OR requested_at>observed_at OR requested_at<observed_at-interval '180 seconds') THEN
   RETURN result||jsonb_build_object('status','unavailable','last_error','request_overdue');
 END IF;
 status:=coalesce(s->>'status','unavailable');
 IF status='healthy' THEN
   IF success_at IS NULL OR valid_until IS NULL OR NOT isfinite(success_at)
      OR NOT isfinite(valid_until) OR success_at>observed_at
      OR success_at<observed_at-interval '600 seconds'
      OR valid_until<>success_at+interval '600 seconds' OR valid_until<observed_at
      OR s->'last_status_code' IS DISTINCT FROM '200'::jsonb
      OR s->>'html_contract' IS DISTINCT FROM 'dufynd_home_v1'
      OR response_bytes IS NULL OR response_bytes NOT BETWEEN 1 AND 131072 THEN
     RETURN result||jsonb_build_object('status','stale','last_error','storefront_success_stale');
   END IF;
   RETURN result||jsonb_build_object('status','healthy','healthy',true);
 END IF;
 IF status='pending' AND NOT s ? 'request_id' THEN
   RETURN result||jsonb_build_object('status','unavailable','last_error','invalid_pending_state');
 END IF;
 IF status NOT IN ('pending','unhealthy','unavailable','stale') THEN status:='unavailable'; END IF;
 RETURN result||jsonb_build_object('status',status);
END
$storefront_read$;

CREATE OR REPLACE FUNCTION public.poll_dufynd_public_storefront_health_v1()
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path TO pg_catalog,public
AS $storefront_poll$
DECLARE
 s jsonb; response record; request_id bigint; observed_at timestamptz; requested_at timestamptz;
 next_poll_at timestamptz; failure text; failures integer:=0; delay_seconds integer;
 response_count integer; queued boolean; clean_html text; head_html text; body_html text;
 tag text; canonical_count integer:=0; canonical_ok boolean:=false;
BEGIN
 IF NOT pg_try_advisory_xact_lock(hashtext('dufynd-public-storefront-health-v1')) THEN
   RETURN public.read_dufynd_public_storefront_health_v1()||jsonb_build_object('poll_busy',true);
 END IF;
 SELECT value INTO s FROM public.dufynd_master_status
 WHERE key='ops.public_storefront_health_v1' FOR UPDATE;
 observed_at:=clock_timestamp();
 IF jsonb_typeof(s) IS DISTINCT FROM 'object' OR s->'enabled' IS DISTINCT FROM 'true'::jsonb THEN
   RETURN public.read_dufynd_public_storefront_health_v1();
 END IF;
 -- Code fixes the complete request/validation scope; the row cannot supply it.
 s:=s||jsonb_build_object('version',1,'endpoint','https://dufynd.de/','canonical','https://dufynd.de',
   'scope','public_storefront_liveness_only','private_observer_evidence',false,
   'full_chain_complete',false,'deployment_revision_verified',false,
   'redirect_chain_verified',false,'final_origin_verified',false,
   'interval_seconds',120,'freshness_seconds',600);
 IF coalesce(s->>'consecutive_failures','') ~ '^[0-9]{1,2}$' THEN
   failures:=least(20,(s->>'consecutive_failures')::integer);
 END IF;
 BEGIN next_poll_at:=(s->>'next_poll_at')::timestamptz;
 EXCEPTION WHEN OTHERS THEN next_poll_at:=null; END;
 IF next_poll_at IS NOT NULL AND (NOT isfinite(next_poll_at)
    OR next_poll_at>observed_at+interval '30 minutes') THEN next_poll_at:=null; END IF;

 IF to_regnamespace('net') IS NULL OR to_regclass('net._http_response') IS NULL THEN
   failure:='pg_net_unavailable';
 ELSIF s ? 'request_id' THEN
   BEGIN requested_at:=(s->>'requested_at')::timestamptz;
   EXCEPTION WHEN OTHERS THEN requested_at:=null; END;
   IF coalesce(s->>'request_id','') !~ '^[1-9][0-9]{0,17}$'
      OR requested_at IS NULL OR NOT isfinite(requested_at) OR requested_at>observed_at THEN
     -- Retain ownership when the saved identity/time is invalid. Automatically
     -- forgetting it could orphan an already queued request and build a backlog.
     s:=s||jsonb_build_object('status','unavailable','last_error','invalid_pending_state',
       'last_error_at',observed_at);
     UPDATE public.dufynd_master_status SET value=s,last_verified_at=observed_at
     WHERE key='ops.public_storefront_health_v1';
     RETURN public.read_dufynd_public_storefront_health_v1();
   ELSE
     request_id:=(s->>'request_id')::bigint;
     -- Bound cardinality/read to the same snapshot. No arbitrary duplicate wins.
     EXECUTE 'select status_code,content_type,content,headers,timed_out,
         error_msg is not null as has_error,created,count(*) over () as receipt_count
       from (select status_code,content_type,content,headers,timed_out,error_msg,created
         from net._http_response where id=$1 limit 2) receipts limit 1'
       INTO response USING request_id;
     response_count:=coalesce(response.receipt_count,0);
     observed_at:=clock_timestamp();
     IF response_count=0 THEN
       IF requested_at>observed_at-interval '60 seconds' THEN
         RETURN public.read_dufynd_public_storefront_health_v1();
       END IF;
       IF to_regclass('net.http_request_queue') IS NOT NULL THEN
         EXECUTE 'select exists(select 1 from net.http_request_queue where id=$1)'
           INTO queued USING request_id;
         IF queued THEN
           s:=s||jsonb_build_object('status','unavailable',
             'last_error','request_dispatch_overdue','last_error_at',observed_at);
           UPDATE public.dufynd_master_status SET value=s,last_verified_at=observed_at
           WHERE key='ops.public_storefront_health_v1';
           RETURN public.read_dufynd_public_storefront_health_v1();
         END IF;
       END IF;
       failure:='response_missing';
     ELSIF response_count<>1 THEN failure:='ambiguous_storefront_receipt';
     ELSIF response.timed_out IS TRUE THEN failure:='transport_timeout';
     ELSIF response.has_error THEN failure:='transport_failure';
     ELSIF response.status_code BETWEEN 300 AND 399 THEN failure:='redirect_response_unverified';
     ELSIF response.status_code IS DISTINCT FROM 200 THEN failure:='http_status_rejected';
     ELSIF response.created IS NULL OR NOT isfinite(response.created)
        OR response.created<requested_at OR response.created>observed_at
        OR response.created<observed_at-interval '600 seconds' THEN failure:='response_not_fresh';
     ELSIF jsonb_typeof(coalesce(response.headers,'{}'::jsonb))<>'object' THEN failure:='response_headers_rejected';
     ELSIF EXISTS(SELECT 1 FROM jsonb_object_keys(coalesce(response.headers,'{}'::jsonb)) h
       WHERE lower(h)='location') THEN failure:='redirect_response_unverified';
     ELSIF btrim(split_part(lower(coalesce(response.content_type,'')),';',1))<>'text/html' THEN
       failure:='content_type_rejected';
     ELSIF response.content IS NULL OR octet_length(response.content)>131072 THEN
       failure:='response_size_rejected';
     ELSE
       -- Signals must be visible document markup, not comments/JS/style text.
       clean_html:=regexp_replace(response.content,
         $rx$<!--.*?-->|<script(?:[[:space:]][^>]*)?>.*?</script[[:space:]]*>|<style(?:[[:space:]][^>]*)?>.*?</style[[:space:]]*>$rx$,'','gis');
       head_html:=substring(clean_html FROM $rx$(?is)<head(?:[[:space:]][^>]*)?>(.*?)</head[[:space:]]*>$rx$);
       body_html:=substring(clean_html FROM $rx$(?is)<body(?:[[:space:]][^>]*)?>(.*?)</body[[:space:]]*>$rx$);
       IF clean_html !~* $rx$^[[:space:]]*<!doctype[[:space:]]+html[[:space:]]*>$rx$
          OR clean_html !~* $rx$</body[[:space:]]*>[[:space:]]*</html[[:space:]]*>[[:space:]]*$rx$
          OR (SELECT count(*) FROM regexp_matches(clean_html,$rx$<html(?:[[:space:]][^>]*)?>$rx$,'gi'))<>1
          OR (SELECT count(*) FROM regexp_matches(clean_html,$rx$<head(?:[[:space:]][^>]*)?>$rx$,'gi'))<>1
          OR (SELECT count(*) FROM regexp_matches(clean_html,$rx$<body(?:[[:space:]][^>]*)?>$rx$,'gi'))<>1
          OR head_html IS NULL OR body_html IS NULL THEN failure:='html_document_rejected';
       ELSIF (SELECT count(*) FROM regexp_matches(head_html,$rx$<title(?:[[:space:]][^>]*)?>[^<]*</title[[:space:]]*>$rx$,'gi'))<>1
          OR head_html !~ $rx$<title(?:[[:space:]][^>]*)?>[^<]*\mDUFYND\M[^<]*</title[[:space:]]*>$rx$ THEN
         failure:='dufynd_identity_rejected';
       ELSE
         FOR tag IN SELECT value[1] FROM regexp_matches(head_html,$rx$(<link[[:space:]][^>]*>)$rx$,'gi') AS matches(value)
         LOOP
           IF tag ~* $rx$[[:space:]]rel[[:space:]]*=[[:space:]]*["']canonical["']$rx$ THEN
             canonical_count:=canonical_count+1;
             canonical_ok:=tag ~ $rx$[[:space:]]href[[:space:]]*=[[:space:]]*["']https://dufynd[.]de["']$rx$
               AND (SELECT count(*) FROM regexp_matches(tag,$rx$[[:space:]]href[[:space:]]*=$rx$,'gi'))=1
               AND (SELECT count(*) FROM regexp_matches(tag,$rx$[[:space:]]rel[[:space:]]*=$rx$,'gi'))=1;
           END IF;
         END LOOP;
         IF canonical_count<>1 OR NOT canonical_ok THEN failure:='canonical_homepage_rejected';
         ELSIF body_html !~* $rx$<section(?:[[:space:]][^>]*)?[[:space:]]data-dufynd-home-audience-stage(?:[[:space:]]|=|>)$rx$
            OR body_html !~ $rx$<a(?:[[:space:]][^>]*)?[[:space:]]href[[:space:]]*=[[:space:]]*["']/duft["']$rx$ THEN
           failure:='homepage_content_rejected';
         END IF;
       END IF;
       IF failure IS NULL THEN
         s:=s||jsonb_build_object('status','healthy','last_success_at',response.created,
           'valid_until',response.created+interval '600 seconds','response_checked_at',observed_at,
           'last_status_code',200,'last_response_bytes',octet_length(response.content),
           'html_contract','dufynd_home_v1','last_error',null,'consecutive_failures',0,
           'next_poll_at',response.created+interval '120 seconds');
         failures:=0; next_poll_at:=response.created+interval '120 seconds';
       END IF;
     END IF;
     -- Metadata is safe only for a unique receipt; never copy provider text.
     IF response_count=1 THEN
       s:=s||jsonb_build_object('last_status_code',CASE WHEN response.status_code BETWEEN 100 AND 599
         THEN response.status_code ELSE null END,'last_response_bytes',octet_length(response.content));
     ELSIF response_count>1 THEN
       s:=s||jsonb_build_object('last_status_code',null,'last_response_bytes',null);
     END IF;
   END IF;
   s:=s-'request_id'-'requested_at';
 END IF;

 IF failure IS NOT NULL THEN
   failures:=least(20,failures+1);
   delay_seconds:=least(1800,(120*power(2,least(failures-1,4)))::integer);
   s:=(s-'request_id'-'requested_at')||jsonb_build_object(
     'status',CASE WHEN failure IN ('http_status_rejected','redirect_response_unverified',
       'html_document_rejected','dufynd_identity_rejected','canonical_homepage_rejected','homepage_content_rejected')
       THEN 'unhealthy' ELSE 'unavailable' END,
     'last_error',failure,'last_error_at',observed_at,'consecutive_failures',failures,
     'next_poll_at',observed_at+make_interval(secs=>delay_seconds));
 ELSIF NOT s ? 'request_id' AND coalesce(next_poll_at,'-infinity'::timestamptz)<=observed_at THEN
   BEGIN
     EXECUTE 'select net.http_get(url:=$1,headers:=$2,timeout_milliseconds:=5000)'
       INTO request_id USING 'https://dufynd.de/',
       '{"Accept":"text/html","User-Agent":"DUFYND-Public-Storefront-Health/1"}'::jsonb;
     IF request_id IS NULL OR request_id<=0 THEN RAISE EXCEPTION 'request id unavailable'; END IF;
     s:=s||jsonb_build_object('request_id',request_id,'requested_at',observed_at,
       'last_attempt_at',observed_at,'next_poll_at',observed_at+interval '120 seconds');
     IF s->>'status' IS DISTINCT FROM 'healthy' THEN s:=s||'{"status":"pending"}'::jsonb; END IF;
   EXCEPTION WHEN OTHERS THEN
     failures:=least(20,failures+1);
     delay_seconds:=least(1800,(120*power(2,least(failures-1,4)))::integer);
     s:=(s-'request_id'-'requested_at')||jsonb_build_object('status','unavailable',
       'last_error','request_enqueue_failed','last_error_at',observed_at,
       'consecutive_failures',failures,'next_poll_at',observed_at+make_interval(secs=>delay_seconds));
   END;
 END IF;
 UPDATE public.dufynd_master_status SET value=s,last_verified_at=observed_at
 WHERE key='ops.public_storefront_health_v1';
 RETURN public.read_dufynd_public_storefront_health_v1();
EXCEPTION WHEN OTHERS THEN
 BEGIN
   UPDATE public.dufynd_master_status SET value=value||jsonb_build_object(
     'status','unavailable','last_error','monitor_internal_error','last_error_at',clock_timestamp()),
     last_verified_at=clock_timestamp() WHERE key='ops.public_storefront_health_v1';
 EXCEPTION WHEN OTHERS THEN
   RAISE LOG 'DUFYND public storefront health status persistence unavailable';
 END;
 RETURN jsonb_build_object('status','unavailable','healthy',false,
   'last_error','monitor_internal_error','scope','public_storefront_liveness_only',
   'private_observer_evidence',false,'full_chain_complete',false,'deployment_revision_verified',false,
   'redirect_chain_verified',false,'final_origin_verified',false);
END
$storefront_poll$;

REVOKE ALL ON FUNCTION public.read_dufynd_public_storefront_health_v1() FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.poll_dufynd_public_storefront_health_v1() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.read_dufynd_public_storefront_health_v1() TO postgres,service_role;
GRANT EXECUTE ON FUNCTION public.poll_dufynd_public_storefront_health_v1() TO postgres,service_role;

-- Reproduced API ambiguity: only receipt selection/cardinality changes below.
CREATE OR REPLACE FUNCTION public.poll_dufynd_public_api_health_v1()
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path TO pg_catalog,public
AS $monitor_poll$
DECLARE
 s jsonb; response record; body jsonb; request_id bigint;
 observed_at timestamptz:=clock_timestamp(); requested_at timestamptz;
 next_poll_at timestamptz; failure text; failures integer:=0; delay_seconds integer;
 response_count integer; queued boolean;
BEGIN
 IF NOT pg_try_advisory_xact_lock(hashtext('dufynd-public-api-health-v1')) THEN
   RETURN public.read_dufynd_public_api_health_v1()||jsonb_build_object('poll_busy',true);
 END IF;
 SELECT value INTO s FROM public.dufynd_master_status
 WHERE key='ops.public_api_health_v1' FOR UPDATE;
 observed_at:=clock_timestamp();
 IF jsonb_typeof(s) IS DISTINCT FROM 'object' OR s->'enabled' IS DISTINCT FROM 'true'::jsonb THEN
   RETURN public.read_dufynd_public_api_health_v1();
 END IF;
 -- Configuration is fixed in code; the status row cannot supply URLs or headers.
 s:=s||jsonb_build_object('version',1,'endpoint','https://scentai-api-kxhe.onrender.com/api/health',
   'scope','public_api_liveness_only','private_observer_evidence',false,
   'full_chain_complete',false,'interval_seconds',120,'freshness_seconds',600);
 IF coalesce(s->>'consecutive_failures','') ~ '^[0-9]{1,2}$' THEN
   failures:=least(20,(s->>'consecutive_failures')::integer);
 END IF;
 BEGIN next_poll_at:=(s->>'next_poll_at')::timestamptz;
 EXCEPTION WHEN OTHERS THEN next_poll_at:=null; END;
 IF next_poll_at IS NOT NULL AND (NOT isfinite(next_poll_at)
    OR next_poll_at>observed_at+interval '30 minutes') THEN next_poll_at:=null; END IF;

 IF to_regnamespace('net') IS NULL OR to_regclass('net._http_response') IS NULL THEN
   failure:='pg_net_unavailable';
 ELSIF s ? 'request_id' THEN
   BEGIN requested_at:=(s->>'requested_at')::timestamptz;
   EXCEPTION WHEN OTHERS THEN requested_at:=null; END;
   IF coalesce(s->>'request_id','') !~ '^[1-9][0-9]{0,17}$'
      OR requested_at IS NULL OR NOT isfinite(requested_at) OR requested_at>observed_at THEN
     failure:='invalid_pending_state';
   ELSE
     request_id:=(s->>'request_id')::bigint;
     EXECUTE 'select status_code,content_type,content,timed_out,error_msg,created,
         count(*) over () as receipt_count from (select status_code,content_type,content,
         timed_out,error_msg,created from net._http_response where id=$1 limit 2) receipts limit 1'
       INTO response USING request_id;
     response_count:=coalesce(response.receipt_count,0);
     observed_at:=clock_timestamp();
     IF response_count=0 THEN
       IF requested_at>observed_at-interval '60 seconds' THEN
         RETURN public.read_dufynd_public_api_health_v1();
       END IF;
       -- An unavailable pg_net worker may still own our queued request. Keep
       -- that identity so repeated cron ticks cannot build a request backlog.
       IF to_regclass('net.http_request_queue') IS NOT NULL THEN
         EXECUTE 'select exists(select 1 from net.http_request_queue where id=$1)'
           INTO queued USING request_id;
         IF queued THEN
           s:=s||jsonb_build_object('status','unavailable',
             'last_error','request_dispatch_overdue','last_error_at',observed_at);
           UPDATE public.dufynd_master_status SET value=s,last_verified_at=observed_at
           WHERE key='ops.public_api_health_v1';
           RETURN public.read_dufynd_public_api_health_v1();
         END IF;
       END IF;
       failure:='response_missing';
     ELSIF response_count<>1 THEN failure:='ambiguous_api_receipt';
     ELSIF coalesce(response.timed_out,false) OR response.error_msg IS NOT NULL THEN
       failure:='transport_failure';
     ELSIF response.status_code IS DISTINCT FROM 200 THEN
       failure:='http_status_rejected';
     ELSIF response.created IS NULL OR NOT isfinite(response.created)
        OR response.created<requested_at OR response.created>observed_at
        OR response.created<observed_at-interval '600 seconds' THEN
       failure:='response_not_fresh';
     ELSIF btrim(split_part(lower(coalesce(response.content_type,'')),';',1))<>'application/json' THEN
       failure:='content_type_rejected';
     ELSIF response.content IS NULL OR octet_length(response.content)>16384 THEN
       failure:='response_size_rejected';
     ELSE
       BEGIN body:=response.content::jsonb;
       EXCEPTION WHEN OTHERS THEN body:=null; END;
       IF jsonb_typeof(body) IS DISTINCT FROM 'object'
          OR body->'ok' IS DISTINCT FROM 'true'::jsonb
          OR body->>'store' IS DISTINCT FROM 'DUFYND' THEN
         failure:='health_payload_rejected';
       ELSE
         s:=s||jsonb_build_object('status','healthy','last_success_at',response.created,
           'valid_until',response.created+interval '600 seconds','response_checked_at',observed_at,
           'last_status_code',200,'last_error',null,'consecutive_failures',0,
           'next_poll_at',response.created+interval '120 seconds');
         failures:=0; next_poll_at:=response.created+interval '120 seconds';
       END IF;
     END IF;
     -- Retain only an HTTP code, never provider response/error text.
     IF response_count=1 THEN s:=s||jsonb_build_object('last_status_code',response.status_code);
     ELSIF response_count>1 THEN s:=s||jsonb_build_object('last_status_code',null); END IF;
   END IF;
   s:=s-'request_id'-'requested_at';
 END IF;

 IF failure IS NOT NULL THEN
   failures:=least(20,failures+1);
   delay_seconds:=least(1800,(120*power(2,least(failures-1,4)))::integer);
   s:=(s-'request_id'-'requested_at')||jsonb_build_object(
     'status',CASE WHEN failure IN ('http_status_rejected','health_payload_rejected')
       THEN 'unhealthy' ELSE 'unavailable' END,
     'last_error',failure,'last_error_at',observed_at,'consecutive_failures',failures,
     'next_poll_at',observed_at+make_interval(secs=>delay_seconds));
 ELSIF NOT s ? 'request_id' AND coalesce(next_poll_at,'-infinity'::timestamptz)<=observed_at THEN
   BEGIN
     EXECUTE 'select net.http_get(url:=$1,headers:=$2,timeout_milliseconds:=5000)'
       INTO request_id USING 'https://scentai-api-kxhe.onrender.com/api/health',
       '{"Accept":"application/json","User-Agent":"DUFYND-Public-API-Health/1"}'::jsonb;
     IF request_id IS NULL OR request_id<=0 THEN RAISE EXCEPTION 'request id unavailable'; END IF;
     s:=s||jsonb_build_object('request_id',request_id,'requested_at',observed_at,
       'last_attempt_at',observed_at,'next_poll_at',observed_at+interval '120 seconds');
     IF s->>'status' IS DISTINCT FROM 'healthy' THEN s:=s||'{"status":"pending"}'::jsonb; END IF;
   EXCEPTION WHEN OTHERS THEN
     failures:=least(20,failures+1);
     delay_seconds:=least(1800,(120*power(2,least(failures-1,4)))::integer);
     s:=(s-'request_id'-'requested_at')||jsonb_build_object('status','unavailable',
       'last_error','request_enqueue_failed','last_error_at',observed_at,
       'consecutive_failures',failures,'next_poll_at',observed_at+make_interval(secs=>delay_seconds));
   END;
 END IF;
 UPDATE public.dufynd_master_status SET value=s,last_verified_at=observed_at
 WHERE key='ops.public_api_health_v1';
 RETURN public.read_dufynd_public_api_health_v1();
EXCEPTION WHEN OTHERS THEN
 BEGIN
   UPDATE public.dufynd_master_status SET value=value||jsonb_build_object(
     'status','unavailable','last_error','monitor_internal_error','last_error_at',clock_timestamp()),
     last_verified_at=clock_timestamp() WHERE key='ops.public_api_health_v1';
 EXCEPTION WHEN OTHERS THEN
   RAISE LOG 'DUFYND public API health status persistence unavailable';
 END;
 RETURN jsonb_build_object('status','unavailable','healthy',false,
   'last_error','monitor_internal_error','scope','public_api_liveness_only',
   'private_observer_evidence',false,'full_chain_complete',false);
END
$monitor_poll$;

-- #847 observer body is preserved exactly apart from this isolated public hook.
CREATE OR REPLACE FUNCTION public.poll_dufynd_observers()
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
declare o public.dufynd_external_observers; r record; body jsonb; url text; headers jsonb; credential_health jsonb; rid bigint; result jsonb; attempted int:=0; retry int; events jsonb;
 checked_at timestamptz; dispatched_at timestamptz; receipt_error text; conditional_fingerprint text;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 begin
  perform public.poll_dufynd_public_api_health_v1();
 exception when others then
  raise log 'DUFYND public API health hook unavailable';
 end;
 begin
  perform public.poll_dufynd_public_storefront_health_v1();
 exception when others then
  raise log 'DUFYND public storefront health hook unavailable';
 end;
 checked_at:=clock_timestamp();
 update public.dufynd_external_observers set health_status='stale',last_error='observer_success_stale'
 where enabled and source_type in ('github_branch','github_pr','github_ci','github_workflow','render','gmail') and health_status in ('healthy','degraded') and coalesce(last_success_at,last_attempt_at,'-infinity')<checked_at-make_interval(secs=>greatest(600,interval_seconds*3));
 if to_regnamespace('net') is null then return jsonb_build_object('available',false); end if;
 for o in select * from public.dufynd_external_observers where request_id is not null and source_type not in ('render','gmail') for update loop
  -- Take wall time after the shared lock and public monitor hook, never at
  -- transaction start: a delayed consumer cannot renew retained evidence.
  if not o.enabled then
   update public.dufynd_external_observers set request_id=null,request_started_at=null,
    request_kind=null,pending_cursor=null where observer_id=o.observer_id;
   continue;
  end if;
  execute 'select status_code,content,headers,timed_out,error_msg,created,count(*) over () as receipt_count from net._http_response where id=$1' into r using o.request_id;
  checked_at:=clock_timestamp();
  if r.receipt_count is null and isfinite(o.request_started_at) and o.request_started_at<=checked_at
   and o.request_started_at>checked_at-interval '60 seconds' then continue; end if;
  -- This binding belongs only to the pending GitHub request. A rejected or
  -- consumed receipt must never be reused by a second poll.
  update public.dufynd_external_observers set request_kind=null,pending_cursor=null
   where observer_id=o.observer_id and source_type in ('github_branch','github_pr','github_ci','github_workflow');
  receipt_error:=case
   when o.request_started_at is null or not isfinite(o.request_started_at) or o.request_started_at>checked_at then 'invalid_observer_request_timestamp'
   when r.receipt_count>1 then 'ambiguous_observer_receipt'
   when r.receipt_count is not null and (r.created is null or not isfinite(r.created)
     or r.created<o.request_started_at or r.created>checked_at) then 'invalid_observer_receipt_timestamp'
   when r.receipt_count is not null and r.created<checked_at-make_interval(secs=>greatest(600,o.interval_seconds*3)) then 'stale_observer_receipt'
   when r.timed_out is true or nullif(r.error_msg,'') is not null then 'external_transport_failure'
   else null end;
  if receipt_error is not null then
   perform public.dufynd_observer_failure(o.observer_id,receipt_error);
   update public.dufynd_external_observers set last_attempt_at=checked_at,
    next_retry_at=checked_at+(next_retry_at-now()) where observer_id=o.observer_id;
   continue;
  end if;
  if r.status_code=304 then
   -- 304 has no replacement body. It can revalidate only the exact validator
   -- and retained snapshot used by this conditional request. Epoch time makes
   -- the binding independent of the consuming session's TimeZone setting.
   conditional_fingerprint:=encode(sha256(convert_to(jsonb_build_array(
    o.etag,o.last_snapshot,extract(epoch from o.last_success_at),
    o.request_id,extract(epoch from o.request_started_at))::text,'UTF8')),'hex');
   if o.source_type not in ('github_branch','github_pr','github_ci','github_workflow')
    or o.request_kind is distinct from 'github_conditional'
    or o.pending_cursor is distinct from conditional_fingerprint
    or nullif(o.etag,'') is null or jsonb_typeof(o.last_snapshot) is distinct from 'object'
    or coalesce(o.last_snapshot->>'sha','') !~ '^[a-f0-9]{40}$'
    or o.last_success_at is null or not isfinite(o.last_success_at) or o.last_success_at>o.request_started_at
    or nullif(r.content,'') is not null
    or (coalesce(r.headers->>'etag',r.headers->>'ETag') is not null
        and coalesce(r.headers->>'etag',r.headers->>'ETag') is distinct from o.etag) then
    update public.dufynd_external_observers set etag=null where observer_id=o.observer_id;
    perform public.dufynd_observer_failure(o.observer_id,'invalid_observer_not_modified');
   update public.dufynd_external_observers set last_attempt_at=checked_at,
    next_retry_at=checked_at+(next_retry_at-now()) where observer_id=o.observer_id;
    continue;
   end if;
   update public.dufynd_external_observers set last_success_at=r.created,health_status='healthy',consecutive_failures=0,last_error=null,
    request_id=null,request_started_at=null,next_retry_at=checked_at+make_interval(secs=>interval_seconds) where observer_id=o.observer_id;
   continue;
  end if;
  if r.status_code is distinct from 200 then
   retry:=case when coalesce(r.headers->>'retry-after','') ~ '^[0-9]{1,5}$' then least(3600,(r.headers->>'retry-after')::int) else null end;
   perform public.dufynd_observer_failure(o.observer_id,case when r.status_code=404 and o.source_type='gmail' then 'gmail_history_expired'
    when r.status_code=429 or (r.status_code=403 and r.headers->>'x-ratelimit-remaining'='0') then 'rate_limited' else 'external_transport_failure' end,coalesce(r.status_code,0),retry);
   update public.dufynd_external_observers set last_attempt_at=checked_at,
    next_retry_at=checked_at+(next_retry_at-now()) where observer_id=o.observer_id;
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
   if result->>'accepted' is distinct from 'true' then
    perform public.dufynd_observer_failure(o.observer_id,'observation_not_accepted');
   update public.dufynd_external_observers set last_attempt_at=checked_at,
    next_retry_at=checked_at+(next_retry_at-now()) where observer_id=o.observer_id;
    continue;
   end if;
   if o.source_type='gmail' and o.request_kind='thread' and o.pending_cursor is not null then
    update public.dufynd_external_observers set last_cursor=case when o.pending_page_token is not null then o.last_cursor else o.pending_cursor end,
      page_token=o.pending_page_token,pending_cursor=null,pending_page_token=null,request_kind=null where observer_id=o.observer_id;
   end if;
   -- capture owns normalization and deduplicated events. Only after acceptance
   -- retain the actual receipt time and replace (including clear) its validator.
   update public.dufynd_external_observers set last_success_at=r.created,last_attempt_at=o.request_started_at,
    next_retry_at=checked_at+make_interval(secs=>interval_seconds),
    etag=nullif(coalesce(r.headers->>'etag',r.headers->>'ETag'),'') where observer_id=o.observer_id;
  exception when others then
   perform public.dufynd_observer_failure(o.observer_id,'invalid_bounded_source_response');
   update public.dufynd_external_observers set last_attempt_at=checked_at,
    next_retry_at=checked_at+(next_retry_at-now()) where observer_id=o.observer_id;
  end;
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
  and request_id is null and next_retry_at<=clock_timestamp() order by next_retry_at,last_attempt_at nulls first limit 1 for update;
 if not found then return jsonb_build_object('attempted',0); end if;
 headers:='{"Accept":"application/json","User-Agent":"DUFYND-Supervisor-V2","X-GitHub-Api-Version":"2022-11-28"}';
 if nullif(o.etag,'') is not null and jsonb_typeof(o.last_snapshot)='object'
  and coalesce(o.last_snapshot->>'sha','') ~ '^[a-f0-9]{40}$'
  and isfinite(o.last_success_at) and o.last_success_at<=clock_timestamp() then
  headers:=headers||jsonb_build_object('If-None-Match',o.etag);
 end if;
 if o.source_type='github_branch' then url:='https://api.github.com/repos/tncommerce/commerce-agents/branches/scentai-mvp';
 elsif o.source_type='github_pr' then url:='https://api.github.com/repos/tncommerce/commerce-agents/pulls/'||o.source_id;
 elsif o.source_type in ('github_ci','github_workflow') then url:='https://api.github.com/repos/tncommerce/commerce-agents/actions/runs/'||o.source_id;
 else return jsonb_build_object('attempted',0); end if;
 dispatched_at:=clock_timestamp();
 execute 'select net.http_get(url:=$1,headers:=$2,timeout_milliseconds:=5000)' into rid using url,headers;
 update public.dufynd_external_observers set request_id=rid,request_started_at=dispatched_at,last_attempt_at=dispatched_at,
  request_kind=case when headers ? 'If-None-Match' then 'github_conditional' else 'github_get' end,
  pending_cursor=case when headers ? 'If-None-Match' then encode(sha256(convert_to(jsonb_build_array(
   o.etag,o.last_snapshot,extract(epoch from o.last_success_at),rid,extract(epoch from dispatched_at))::text,'UTF8')),'hex') else null end
  where observer_id=o.observer_id;
 return jsonb_build_object('attempted',1);
end $function$;

REVOKE ALL ON FUNCTION public.poll_dufynd_public_api_health_v1() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.poll_dufynd_public_api_health_v1() TO postgres,service_role;
REVOKE ALL ON FUNCTION public.poll_dufynd_observers() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.poll_dufynd_observers() TO postgres,service_role;
