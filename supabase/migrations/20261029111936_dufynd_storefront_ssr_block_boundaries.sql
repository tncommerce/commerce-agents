-- Forward correction for the exact public SSR receipt 22710 (29 Oct 2026).
-- PostgreSQL makes a top-level alternation greedy even with inner .*?.
-- Force the whole removal match to the nearest complete comment/script/style
-- block; preserve all document, provenance, transport, size and scope guards.
-- https://www.postgresql.org/docs/17/functions-matching.html#POSIX-MATCHING-RULES
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
         $rx$(?:<!--.*?-->|<script(?:[[:space:]][^>]*)?>.*?</script[[:space:]]*>|<style(?:[[:space:]][^>]*)?>.*?</style[[:space:]]*>){1,1}?$rx$,'','gis');
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

REVOKE ALL ON FUNCTION public.poll_dufynd_public_storefront_health_v1() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.poll_dufynd_public_storefront_health_v1() TO postgres,service_role;
