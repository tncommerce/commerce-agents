-- A response can already be available before the next two-minute consumer tick.
-- Allow one normal 120s cycle plus 60s scheduling slack for pending diagnostics.
-- This replaces only the reader: no success timestamp, poll/transport timeout,
-- freshness limit, permission, provider evidence or cron schedule is changed.
-- CREATE OR REPLACE retains the existing restricted function ACL and owner.

CREATE OR REPLACE FUNCTION public.read_dufynd_public_api_health_v1()
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path TO pg_catalog,public
AS $monitor_read$
DECLARE
 s jsonb; result jsonb; success_at timestamptz; valid_until timestamptz;
 requested_at timestamptz; observed_at timestamptz:=clock_timestamp();
 status text;
BEGIN
 SELECT value INTO s FROM public.dufynd_master_status WHERE key='ops.public_api_health_v1';
 IF jsonb_typeof(s) IS DISTINCT FROM 'object' THEN s:='{}'::jsonb; END IF;
 result:=jsonb_build_object(
   'version',1,'enabled',s->'enabled'='true'::jsonb,
   'endpoint','https://scentai-api-kxhe.onrender.com/api/health',
   'scope','public_api_liveness_only','private_observer_evidence',false,
   'full_chain_complete',false,'healthy',false,'observed_at',observed_at,
   'interval_seconds',120,'freshness_seconds',600,
   'last_success_at',s->'last_success_at','valid_until',s->'valid_until',
   'last_attempt_at',s->'last_attempt_at','next_poll_at',s->'next_poll_at',
   'last_error',s->'last_error','last_status_code',s->'last_status_code',
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
 status:=coalesce(s->>'status','unavailable');
 IF status='healthy' THEN
   IF success_at IS NULL OR valid_until IS NULL OR NOT isfinite(success_at)
      OR NOT isfinite(valid_until) OR success_at>observed_at
      OR success_at<observed_at-interval '600 seconds'
      OR valid_until<>success_at+interval '600 seconds' OR valid_until<observed_at
      OR s->'last_status_code' IS DISTINCT FROM '200'::jsonb THEN
     RETURN result||jsonb_build_object('status','stale','last_error','api_success_stale');
   END IF;
   RETURN result||jsonb_build_object('status','healthy','healthy',true);
 END IF;
 IF status='pending' AND (requested_at IS NULL OR NOT isfinite(requested_at)
    OR requested_at>observed_at OR requested_at<observed_at-interval '180 seconds') THEN
   RETURN result||jsonb_build_object('status','unavailable','last_error','request_overdue');
 END IF;
 IF status NOT IN ('pending','unhealthy','unavailable','stale') THEN status:='unavailable'; END IF;
 RETURN result||jsonb_build_object('status',status);
END
$monitor_read$;
