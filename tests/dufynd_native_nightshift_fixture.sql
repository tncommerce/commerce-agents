-- Disposable PostgreSQL ONLY. Shape of the eleven observed cron registrations;
-- not a pg_cron installation and not evidence that production jobs were executed.
create schema cron;
create table cron.job(jobid bigint primary key,jobname text,schedule text,command text,active boolean);
insert into cron.job values
 (1,'dufynd-supervisor-v2-health','*/2 * * * *','select public.reconcile_dufynd_supervisor_v2();',true),
 (2,'dufynd-thin-v1-free','1-59/2 * * * *','select public.run_dufynd_thin_v1();',true),
 (3,'dufynd-free-planner-v1','*/2 * * * *','select public.plan_dufynd_free_work_v1();',true),
 (4,'dufynd-content-reuse-worker-v1','*/2 * * * *','select public.run_dufynd_content_worker_v1();',true),
 (5,'dufynd-integrity-sentinel-v1','*/5 * * * *','select public.audit_dufynd_integrity_with_gmail_v1();',true),
 (6,'dufynd-affiliate-evidence-worker-v1','*/2 * * * *','select public.run_dufynd_affiliate_worker_v1();',true),
 (7,'dufynd-content-backlog-worker-v1','*/2 * * * *','select public.run_dufynd_content_backlog_worker_v1();',true),
 (8,'dufynd-content-packet-worker-v1','*/2 * * * *','select public.run_dufynd_content_packet_worker_v1();',true),
 (9,'dufynd-first-money-measurement-worker-v1','*/2 * * * *','select public.run_dufynd_measurement_worker_v1();',true),
 (10,'dufynd-content-performance-learning-v1','*/10 * * * *','select public.run_dufynd_content_performance_cycle_v1();',true),
 (11,'dufynd-ceo-v2-growth-loop','*/10 * * * *','select public.run_dufynd_ceo_with_missions_v1();',true);

-- Only the old CEO business action is a sentinel stub; real mission routing and
-- real supervisor/claim/update RPCs are loaded from repository migrations.
create function public.run_dufynd_ceo_safe_cycle_v1() returns jsonb language plpgsql as $$
begin
 insert into public.dufynd_master_status(key,value)
 values('test.legacy_ceo','{"calls":1}') on conflict(key) do update
 set value=jsonb_build_object('calls',(dufynd_master_status.value->>'calls')::int+1);
 return '{"state":"legacy_ceo_called"}'::jsonb;
end $$;

insert into public.dufynd_master_status(key,value,last_verified_at) values
 ('jarvis.first_money_measurement_v1','{"version":2,"traffic_provenance":"visitor_class_excludes_qa_sessions_and_unclassified_history","clickout_is_sale":false,"new_spend_usd":0,"internal_qa_events":76,"unclassified_events":861,"postlaunch_landing_sessions":0,"postlaunch_product_views":0,"postlaunch_offer_views":0,"postlaunch_merchant_clickouts":0,"network_ingestion_connected":false,"experiment_id":"synthetic_sql_fixture","content_id":"synthetic_sql_fixture"}',now());
insert into public.dufynd_master_status(key,value,last_verified_at)
select 'jarvis.mission_result.v1:autonomy_acceptance_20261010:2',jsonb_build_object(
 'artifact',a,'artifact_md5',md5(a::text),'quality_verified',true,'lease_released',true,
 'task_id','mission:v1:autonomy_acceptance_20261010:2'),now()
from (select '{"publishing_allowed":false,"paid_generation_allowed":false,"new_spend_usd":0,"concept":"Synthetic archived SQL fixture"}'::jsonb a) s;
