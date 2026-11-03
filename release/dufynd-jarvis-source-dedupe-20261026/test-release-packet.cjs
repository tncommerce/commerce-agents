// New release/rollback rehearsal only. Existing 31-case dedupe suite is not rerun.
// Disposable PostgreSQL-WASM; no network, DSN, credentials or deployment path.
const { PGlite } = require('@electric-sql/pglite');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..');
const read = file => fs.readFileSync(path.join(__dirname,file),'utf8');
const baseline = JSON.parse(read('production-baseline.json'));
const manifest = JSON.parse(read('manifest.json'));
const cases = [];
const ok = (condition, label) => { if(!condition)throw Error(label);cases.push(label); };
(async()=>{
 const db = new PGlite();
 try {
  for(const [file,expected] of Object.entries(manifest.files)) {
   if(crypto.createHash('sha256').update(read(file)).digest('hex')!==expected)throw Error('File drift: '+file);
  }
  ok(crypto.createHash('sha256').update(fs.readFileSync(path.join(root,manifest.migration_path))).digest('hex')===manifest.migration_sha256,
    '01 exact reviewed migration and package hashes');
  await db.exec(fs.readFileSync(path.join(root,'tests/dufynd_budget_schema_fixture.sql'),'utf8'));
  await db.exec(`
   alter table dufynd_autonomy_tasks add column budget_class text,add column resource_scope jsonb,
     add column durability_policy text,add column durable_payload jsonb,add column forbidden_actions jsonb;
   create table dufynd_content_assets(id text primary key,content_id text,platform text);
   create table dufynd_content_workflows(asset_id text primary key,revision_fingerprint text,evidence jsonb);
   create function public.get_dufynd_next_autonomous_action() returns jsonb language plpgsql as $$
     begin raise exception 'Release scripts must not invoke the queue';end $$;
   create function public.read_dufynd_first_money_runtime() returns jsonb language plpgsql as $$
     begin raise exception 'Release scripts must not invoke runtime/planner';end $$;
   insert into dufynd_autonomy_tasks(task_id,domain,title,instruction,status)
     values('release-fixture-done','supervisor','isolated fixture','never run','done');
   insert into dufynd_master_status(key,category,value,priority,last_verified_at)
     values('jarvis.business_source_dedupe_v1','jarvis','{"source_fingerprint":"preserve-me","task_id":"release-fixture-done"}',100,'2026-10-26T10:00:00Z');
   insert into dufynd_content_assets values('release-fixture','fixture-content','instagram');
   insert into dufynd_content_workflows values('release-fixture','fixture-revision','{"publication_observation":{"status":"unknown"}}');
  `);
  await db.exec(read('baseline-planner.sql'));
  await db.exec(`revoke execute on function public.plan_dufynd_autonomous_business_work_v1() from public,anon,authenticated;
    grant execute on function public.plan_dufynd_autonomous_business_work_v1() to service_role,postgres;`);
  const state = async()=>(await db.query(`select pg_get_functiondef(p.oid) definition,
   md5(pg_get_functiondef(p.oid)) definition_md5,p.proacl::text acl,pg_get_userbyid(p.proowner) owner,
   p.prosecdef security_definer,p.proconfig config,obj_description(p.oid,'pg_proc') comment
   from pg_proc p where p.oid='public.plan_dufynd_autonomous_business_work_v1()'::regprocedure`)).rows[0];
  const rows = async()=>JSON.stringify((await db.query(`select
   (select jsonb_agg(to_jsonb(t) order by task_id) from public.dufynd_autonomy_tasks t) tasks,
   (select jsonb_agg(to_jsonb(m) order by key) from public.dufynd_master_status m) checkpoints,
   (select jsonb_agg(to_jsonb(a) order by id) from public.dufynd_content_assets a) assets,
   (select jsonb_agg(to_jsonb(w) order by asset_id) from public.dufynd_content_workflows w) workflows`)).rows[0]);
  const untouched = await rows();
  const before = await state();
  ok(before.definition===baseline.definition && before.definition_md5===baseline.definition_md5 && before.acl===baseline.acl,
    '02 captured production baseline reproduced byte for byte');
  await db.exec(read('apply.sql'));
  ok((await state()).definition_md5===manifest.after_planner_md5,'03 guarded apply commits exact reviewed planner');
  ok((await rows())===untouched,'04 apply preserves tasks, checkpoint, assets and workflows byte for byte');
  await db.exec(read('postflight.sql'));
  ok(true,'05 exact function hashes, owner, ACL and invoker postflight passes');
  const helperOid=(await db.query("select 'public.read_dufynd_business_source_v1(jsonb)'::regprocedure::oid oid")).rows[0].oid;
  await db.exec(read('rollback.sql'));
  ok(JSON.stringify(await state())===JSON.stringify(before),'06 rollback restores complete planner definition and permissions');
  ok((await rows())===untouched,'07 rollback preserves tasks, checkpoint, assets and workflows byte for byte');
  ok((await db.query("select 'public.read_dufynd_business_source_v1(jsonb)'::regprocedure::oid oid")).rows[0].oid===helperOid,
    '08 private helper retained without drop or recreation');
  await db.exec(read('apply.sql'));
  ok((await state()).definition_md5===manifest.after_planner_md5 && await rows()===untouched,
    '09 reapply after rollback preserves the existing checkpoint and task history');
  const reject = async(sql,label,expectedFragment)=>{
   let error;
   try{await db.exec(sql);}catch(e){error=e;}
   await db.exec('rollback;');
   ok(Boolean(error)&&error.message.includes(expectedFragment),label);
  };
  await reject(read('apply.sql'),'10 double apply fails closed instead of silently overwriting state','unexpected function definition');
  await db.exec(`comment on function public.plan_dufynd_autonomous_business_work_v1() is 'unexpected operator change';`);
  await reject(read('rollback.sql'),'11 rollback refuses an unexpected function metadata change','unexpected owner, ACL');
  await db.exec(`comment on function public.plan_dufynd_autonomous_business_work_v1() is null;`);
  await db.exec('grant execute on function public.plan_dufynd_autonomous_business_work_v1() to anon;');
  await reject(read('rollback.sql'),'12 rollback refuses unexpected additional role access','unexpected owner, ACL');
  await db.exec('revoke execute on function public.plan_dufynd_autonomous_business_work_v1() from anon;');
  await db.exec(read('rollback.sql'));
  await db.exec('set role service_role;');
  await reject(read('apply.sql'),'13 non-owner deployment role fails closed','execute as the verified postgres owner');
  await db.exec('reset role;');
  await db.exec('alter function public.read_dufynd_first_money_runtime() rename to release_test_missing_runtime;');
  await reject(read('apply.sql'),'14 missing runtime dependency prevents application','required planner/runtime function missing');
  await db.exec('alter function public.release_test_missing_runtime() rename to read_dufynd_first_money_runtime;');
  const badPostflight=read('apply.sql').replace(manifest.after_planner_md5,'00000000000000000000000000000000');
  await reject(badPostflight,'15 failing postflight aborts the transaction','unexpected function definition');
  ok(JSON.stringify(await state())===JSON.stringify(before) && await rows()===untouched,
    '16 failed deployment leaves prior definition, ACL and business rows unchanged');
  await db.exec('grant execute on function public.read_dufynd_business_source_v1(jsonb) to authenticated;');
  await reject(read('apply.sql'),'17 reapply refuses altered inert helper permissions','unexpected owner, ACL');
  await db.exec('revoke execute on function public.read_dufynd_business_source_v1(jsonb) from authenticated;');
  await db.exec(read('apply.sql'));
  const badRollback=read('rollback.sql').replace(baseline.definition_md5,'00000000000000000000000000000000');
  await reject(badRollback,'18 failing rollback postflight aborts the rollback','unexpected function definition');
  ok((await state()).definition_md5===manifest.after_planner_md5 && await rows()===untouched,
    '19 failed rollback preserves new planner and business rows');
  await db.exec(read('rollback.sql'));
  ok(JSON.stringify(await state())===JSON.stringify(before) && await rows()===untouched,
    '20 final rollback returns to the exact captured production baseline');
  console.log(JSON.stringify({engine:(await db.query('select version()')).rows[0].version,
    passed:cases.length,cases,scope:'new release payload rehearsal only; offline PostgreSQL-WASM; no native concurrent-lock claim',
    productionExecution:false,existingDedupeSuiteRerun:false,migrationSha256:manifest.migration_sha256},null,2));
 }finally{await db.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
