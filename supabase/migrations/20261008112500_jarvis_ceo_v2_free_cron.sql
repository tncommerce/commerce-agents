-- Keep the CEO orchestration actively checking for newly real, zero-cost work.
-- Safe cycle is bounded to one certified free worker and no external actions.
select cron.schedule(
  'dufynd-ceo-v2-growth-loop',
  '*/10 * * * *',
  'select public.run_dufynd_ceo_safe_cycle_v1();'
);