-- Forward-only purchase transport diagnostics. No historical report/hash,
-- target, scheduler, retry policy, merchant contract or business field changes.
-- The existing evaluator stays unchanged. Successful reports stay unchanged.
-- pg_net response IDs are not unique: reject ambiguity rather than pick a row.
create or replace function public.poll_dufynd_purchase_verification(p_execution_id uuid)
returns jsonb
language plpgsql
security invoker
set search_path to 'public'
as $function$
declare
  e public.dufynd_execution_runs;
  product record;
  shipping record;
  reply record;
  rid bigint;
  sid bigint;
  audit jsonb;
  checked_at timestamptz;
  transport jsonb := '{"version":1}'::jsonb;
begin
  select * into e from public.dufynd_execution_runs
  where execution_id=p_execution_id for update;
  if e.handler_id<>'purchase_destination_freshness_audit'
    or not public.dufynd_execution_contract_valid(e.execution_id) then return null; end if;
  if e.purchase_request_id is null then
    execute 'select net.http_get(url:=$1,headers:=$2,timeout_milliseconds:=10000)' into rid using
      'https://www.perfumetrader.de/de/paco-rabanne-1-million-eau-de-toilette-100-ml',
      '{"Cache-Control":"no-cache","User-Agent":"DUFYND-Exact-Purchase-Verification/1"}'::jsonb;
    execute 'select net.http_get(url:=$1,headers:=$2,timeout_milliseconds:=10000)' into sid using
      'https://www.perfumetrader.de/de/versandbedingungen',
      '{"Cache-Control":"no-cache","User-Agent":"DUFYND-Exact-Purchase-Verification/1"}'::jsonb;
    update public.dufynd_execution_runs set purchase_request_id=rid,
      purchase_shipping_request_id=sid,purchase_requested_at=now()
    where execution_id=e.execution_id;
    return null;
  end if;

  -- Count and read each ID in one snapshot, bounded at two matching rows.
  -- Never retain raw error text, even inside the diagnostic projection.
  execute 'select count(*) over () as response_count,status_code,content,created,
      timed_out,error_msg is not null as has_error
    from (select status_code,content,created,timed_out,error_msg
      from net._http_response where id=$1 limit 2) responses limit 1'
    into product using e.purchase_request_id;
  execute 'select count(*) over () as response_count,status_code,content,created,
      timed_out,error_msg is not null as has_error
    from (select status_code,content,created,timed_out,error_msg
      from net._http_response where id=$1 limit 2) responses limit 1'
    into shipping using e.purchase_shipping_request_id;
  -- A valid receipt can arrive after transaction/statement start or a row-lock
  -- wait. Compare source time with the real clock after both receipt reads.
  checked_at := clock_timestamp();

  if e.purchase_requested_at is null or not isfinite(e.purchase_requested_at)
    or e.purchase_requested_at>checked_at then
    -- Existing IDs without a real request time cannot establish source order.
    -- This is a request-binding error, not a fabricated response failure.
    audit := jsonb_build_object('version',1,'decision','transport_unverified','observed_at',checked_at);
    transport := transport || '{"request_error_class":"request_time_invalid"}'::jsonb;
  elsif coalesce(product.response_count,0)=0 or coalesce(shipping.response_count,0)=0 then
    if e.purchase_requested_at>=checked_at-interval '60 seconds' then return null; end if;
    audit := jsonb_build_object('version',1,'decision','transport_unverified','observed_at',checked_at);
  elsif product.response_count<>1 or shipping.response_count<>1
    or product.timed_out or shipping.timed_out or product.has_error or shipping.has_error
    or product.created is null or shipping.created is null
    or not isfinite(product.created) or not isfinite(shipping.created)
    or product.created>checked_at or shipping.created>checked_at
    or product.created<e.purchase_requested_at or shipping.created<e.purchase_requested_at
    or product.created<checked_at-interval '5 minutes'
    or shipping.created<checked_at-interval '5 minutes' then
    audit := jsonb_build_object('version',1,'decision','transport_unverified','observed_at',checked_at);
  else
    audit := public.evaluate_dufynd_purchase_page(e.payload,coalesce(product.content,''),
      coalesce(shipping.content,''),coalesce(product.status_code,0),coalesce(shipping.status_code,0));
    audit := audit || jsonb_build_object('observed_at',least(product.created,shipping.created),
      'source','fixed_https_merchant_pg_net','product_request_id',e.purchase_request_id,
      'shipping_request_id',e.purchase_shipping_request_id);
    if audit->>'decision' is distinct from 'transport_unverified' then return audit; end if;
  end if;

  -- Exactly two fixed labels and five bounded fields per response. Unknown
  -- status/body/timeout stays null; missing or duplicate rows provide no data.
  for reply in
    select 'product' as name,coalesce(product.response_count,0) as response_count,
      product.status_code as status_code,octet_length(product.content) as response_bytes,
      product.created as response_at,product.timed_out as timed_out,product.has_error as has_error
    union all
    select 'shipping',coalesce(shipping.response_count,0),shipping.status_code,
      octet_length(shipping.content),shipping.created,shipping.timed_out,shipping.has_error
  loop
    transport := transport || jsonb_build_object(reply.name,jsonb_build_object(
      'response_state',case when reply.response_count=0 then 'missing'
        when reply.response_count<>1 then 'ambiguous' else 'received' end,
      'error_class',case
        when reply.response_count=0 then 'response_missing'
        when reply.response_count<>1 then 'duplicate_response'
        when reply.timed_out then 'timeout'
        when reply.has_error then 'transport_error'
        when reply.response_at is null then 'response_time_unknown'
        when not isfinite(reply.response_at) then 'response_time_nonfinite'
        when reply.response_at>checked_at then 'response_in_future'
        when reply.response_at<e.purchase_requested_at then 'response_before_request'
        when reply.response_at<checked_at-interval '5 minutes' then 'response_stale'
        when reply.status_code is null or reply.status_code not between 100 and 599 then 'http_status_unknown'
        when reply.status_code<>200 then 'http_status_error'
        when reply.response_bytes>250000 then 'body_too_large'
        when reply.response_bytes is null then 'body_unknown'
        else 'none' end,
      'http_status',case when reply.response_count=1 and reply.status_code between 100 and 599
        then reply.status_code else null end,
      'response_bytes',case when reply.response_count=1 then reply.response_bytes else null end,
      'timed_out',case when reply.response_count=1 then reply.timed_out else null end
    ));
  end loop;
  return audit || jsonb_build_object('transport',transport);
end;
$function$;

-- Preserve the existing private, invoker-only execution boundary.
revoke all on function public.poll_dufynd_purchase_verification(uuid)
  from public, anon, authenticated;
grant execute on function public.poll_dufynd_purchase_verification(uuid)
  to postgres, service_role;
