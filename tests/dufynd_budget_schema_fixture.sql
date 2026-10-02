-- Minimal pre-Phase-1 schema; production tests also run against actual Supabase.
create role anon; create role authenticated; create role service_role bypassrls;
create table public.dufynd_autonomy_tasks (
 task_id text primary key,domain text not null,title text not null,instruction text not null,
 status text not null default 'ready',priority int default 50,requires_human_approval boolean not null default false,
 dependencies jsonb not null default '[]',evidence text,owner text,updated_at timestamptz default now()
);
create table public.dufynd_jarvis_budget_windows (
 budget_id text primary key,title text,status text,model text,cap_usd numeric,max_runs int,approved_decision_id text
);
create table public.dufynd_agent_runs(id uuid primary key default gen_random_uuid(),agent_name text,decisions jsonb);
create table public.dufynd_human_decisions(decision_id text primary key,status text,decision jsonb);
create table public.dufynd_master_status(key text primary key,category text,value jsonb,priority int,last_verified_at timestamptz);
create table public.dufynd_jarvis_inbox(
 inbox_id bigserial primary key,event_type text not null,source_type text not null,source_id text,payload jsonb not null default '{}',
 status text not null default 'pending',available_at timestamptz default now(),claimed_at timestamptz,processed_at timestamptz,
 attempts int not null default 0,last_error text,created_at timestamptz default now(),updated_at timestamptz default now());
create function public.get_dufynd_jarvis_budget_status(text) returns jsonb language sql as $$ select '{"can_run":false}'::jsonb $$;
