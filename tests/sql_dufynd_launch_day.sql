-- Production-schema regression, fixtures MUST roll back. No real traffic or network calls.
begin;
do $$
declare r jsonb; n int; before_count int; kind text; variant text;
begin
 update public.dufynd_master_status set value=jsonb_set(value,'{first_money_schedule}',jsonb_build_object(
 'content_id','launch_fixture','experiment_id','launch_experiment',
 'instagram',(now()-interval '1 hour')::text,'tiktok',(now()-interval '30 minutes')::text))
 where key='continuity.checkpoint.ceo_radar';
 select count(*) into before_count from public.dufynd_autonomy_tasks where task_id like 'first-money-signal:%';
 -- Every valid event type shares one ingest bucket and a null-product landing is supported.
 for kind in select unnest(array['page_view','fragrance_detail_view','offer_section_view','offer_section_open','merchant_clickout']) loop
 insert into public.scentai_analytics_events(id,event_id,occurred_at,session_key,event,product_id,acquisition_source,campaign_id,content_id)
 values((select coalesce(max(id),0)+1 from public.scentai_analytics_events),gen_random_uuid(),now(),'launch_fixture_session',kind,
 case when kind='page_view' then null else 'SC-RABANNE-1-MILLION-EDT-100' end,'instagram','launch_experiment','launch_fixture');
 end loop;
 select count(*) into n from public.dufynd_autonomy_tasks where task_id like 'first-money-signal:%';
 if n<>before_count+1 then raise exception '10-minute bucket dedupe failed'; end if;
 r:=public.read_dufynd_first_money_runtime();
 if r->'funnel'->>'landing_sessions'<>'1' or r->'funnel'->>'product_views'<>'1'
 or r->'funnel'->>'offer_views'<>'1' or r->'funnel'->>'offer_opens'<>'1' or r->'funnel'->>'merchant_clickouts'<>'1'
 or r->>'decision_state'<>'purchase_interest_reached' or r->>'next_evidence'<>'affiliate_transaction_evidence'
 or r->'sales_truth'->>'clickout_is_sale'<>'false' or r->'sales_truth'->>'network_ingestion_connected'<>'false'
 then raise exception 'launch funnel or sales truth invalid: %',r; end if;
 -- Separate content, campaign, source, product, prelaunch and future traffic cannot change the funnel/queue.
 for variant in select unnest(array['content','campaign','source','product','prelaunch','future','tiktok_before']) loop
 insert into public.scentai_analytics_events(id,event_id,occurred_at,session_key,event,product_id,acquisition_source,campaign_id,content_id)
 values((select coalesce(max(id),0)+1 from public.scentai_analytics_events),gen_random_uuid(),
 case variant when 'prelaunch' then now()-interval '2 hours' when 'future' then now()+interval '1 hour'
 when 'tiktok_before' then now()-interval '45 minutes' else now() end,
 'unrelated_session','merchant_clickout',case when variant='product' then 'SC-PDM-DELINA-EDP-75' else 'SC-RABANNE-1-MILLION-EDT-100' end,
 case variant when 'source' then 'youtube' when 'tiktok_before' then 'tiktok' else 'instagram' end,
 case when variant='campaign' then 'other_experiment' else 'launch_experiment' end,
 case when variant='content' then 'unrelated_content' else 'launch_fixture' end);
 end loop;
 if (select count(*) from public.dufynd_autonomy_tasks where task_id like 'first-money-signal:%')<>n then raise exception 'unrelated traffic queued work'; end if;
 if public.read_dufynd_first_money_runtime()->'funnel' is distinct from r->'funnel' then raise exception 'unrelated traffic polluted funnel'; end if;
 if public.read_dufynd_supervisor_audit()->'first_money_runtime'->'funnel' is distinct from r->'funnel' then raise exception 'audit missing revenue evidence'; end if;
 if has_function_privilege('anon','public.read_dufynd_first_money_runtime()','execute') then raise exception 'public runtime exposure'; end if;
end $$;
rollback;
