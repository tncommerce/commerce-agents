// Delta test for the new single-statement tool payloads. No prior suite rerun.
const { PGlite } = require('@electric-sql/pglite');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=name=>fs.readFileSync(path.join(__dirname,name),'utf8');
const manifest=JSON.parse(read('manifest.json'));
const cases=[];
const ok=(value,label)=>{if(!value)throw Error(label);cases.push(label);};
(async()=>{
 const db=new PGlite();
 try{
  await db.exec(fs.readFileSync(path.join(root,'tests/dufynd_budget_schema_fixture.sql'),'utf8'));
  await db.exec(`alter table dufynd_autonomy_tasks add column budget_class text,add column resource_scope jsonb,
   add column durability_policy text,add column durable_payload jsonb,add column forbidden_actions jsonb;
   create table dufynd_content_assets(id text,content_id text,platform text);
   create table dufynd_content_workflows(asset_id text,revision_fingerprint text,evidence jsonb);
   create function get_dufynd_next_autonomous_action() returns jsonb language plpgsql as $$
     begin raise exception 'Forbidden runtime call during installation';end $$;
   create function read_dufynd_first_money_runtime() returns jsonb language plpgsql as $$
     begin raise exception 'Forbidden runtime call during installation';end $$;
   insert into dufynd_master_status values('jarvis.business_source_dedupe_v1','jarvis',
     '{"source_fingerprint":"keep-existing"}',100,'2026-10-26T10:00:00Z');`);
  await db.exec(read('baseline-planner.sql'));
  await db.exec(`revoke execute on function plan_dufynd_autonomous_business_work_v1() from public,anon,authenticated;
   grant execute on function plan_dufynd_autonomous_business_work_v1() to service_role,postgres;`);
  const state=async()=>(await db.query(`select md5(pg_get_functiondef(
   'public.plan_dufynd_autonomous_business_work_v1()'::regprocedure)) planner,
   to_regprocedure('public.read_dufynd_business_source_v1(jsonb)') is not null helper,
   (select to_jsonb(m) from dufynd_master_status m where key='jarvis.business_source_dedupe_v1') checkpoint,
   (select count(*) from dufynd_autonomy_tasks) tasks,
   current_setting('lock_timeout') lock_timeout,current_setting('statement_timeout') statement_timeout`)).rows[0];
  const initial=await state();
  const reject=async(sql,label)=>{
   let error;try{await db.exec(sql);}catch(e){error=e;}
   ok(Boolean(error)&&error.message.includes('unexpected function definition'),label);
  };
  await reject(read('apply-body.sql').replace(manifest.after_planner_md5,'00000000000000000000000000000000'),
   '01 single-statement apply rejects an injected failing postflight');
  ok(JSON.stringify(await state())===JSON.stringify(initial),
   '02 failed atomic apply restores original planner, absent helper, checkpoint and session settings without client ROLLBACK');
  await db.exec(read('apply-body.sql'));
  const applied=await state();
  ok(applied.planner===manifest.after_planner_md5 && applied.helper && applied.tasks===initial.tasks,
   '03 exact tool apply payload succeeds without invoking planner or creating tasks');
  ok(JSON.stringify(applied.checkpoint)===JSON.stringify(initial.checkpoint) &&
   applied.lock_timeout===initial.lock_timeout && applied.statement_timeout===initial.statement_timeout,
   '04 successful atomic apply preserves checkpoint and restores session timeout settings');
  await reject(read('rollback-body.sql').replace(manifest.before_planner_md5,'00000000000000000000000000000000'),
   '05 single-statement rollback rejects an injected failing postflight');
  ok(JSON.stringify(await state())===JSON.stringify(applied),
   '06 failed atomic rollback preserves the applied planner and all saved state without client ROLLBACK');
  await db.exec(read('rollback-body.sql'));
  const rolledBack=await state();
  ok(rolledBack.planner===manifest.before_planner_md5 && rolledBack.helper &&
   rolledBack.tasks===initial.tasks && JSON.stringify(rolledBack.checkpoint)===JSON.stringify(initial.checkpoint),
   '07 exact tool rollback payload restores baseline while retaining private helper and checkpoint');
  ok(rolledBack.lock_timeout===initial.lock_timeout && rolledBack.statement_timeout===initial.statement_timeout,
   '08 successful atomic rollback leaves no timeout session-state change');
  console.log(JSON.stringify({passed:cases.length,cases,productionExecution:false,
   engine:(await db.query('select version()')).rows[0].version,
   scope:'single-statement migration payloads in offline PostgreSQL-WASM; Supabase transport and history registration not executed'},null,2));
 }finally{await db.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
