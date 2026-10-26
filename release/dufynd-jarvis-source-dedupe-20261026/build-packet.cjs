// Builds reviewable SQL payloads. It never opens a database or invokes a deploy.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..');
const read = name => fs.readFileSync(path.join(__dirname, name), 'utf8');
const write = (name, value) => fs.writeFileSync(path.join(__dirname, name), value);
const sha256 = value => crypto.createHash('sha256').update(value).digest('hex');
const baseline = JSON.parse(read('production-baseline.json'));
const expected = JSON.parse(read('expected-functions.json'));
const planner = expected.find(row => row.name.startsWith('plan_'));
const helper = expected.find(row => row.name.startsWith('read_'));
const migrationPath = 'supabase/migrations/20261026083433_jarvis_business_source_dedupe.sql';
const migration = fs.readFileSync(path.join(root, migrationPath), 'utf8');
if (sha256(migration) !== '65caae22624b26fd925d8e341a78696ed9e21e9b3ef45ced49d6335f15a04eb4') {
  throw new Error('The reviewed migration changed; do not regenerate against a different payload.');
}
const functionCheck = (signature, md5) => `
  select * into p from pg_proc where oid=to_regprocedure('${signature}');
  if not found or md5(pg_get_functiondef(p.oid)) is distinct from '${md5}' then
    raise exception 'DUFYND release guard: unexpected function definition: ${signature}';
  end if;
  if pg_get_userbyid(p.proowner)<>'postgres' or p.prosecdef or
     p.proconfig is distinct from array['search_path=public']::text[] or
     obj_description(p.oid,'pg_proc') is not null or
     (select array_agg(a::text order by a::text) from unnest(p.proacl) a)
       is distinct from array['postgres=X/postgres','service_role=X/postgres']::text[] then
    raise exception 'DUFYND release guard: unexpected owner, ACL, invoker mode, search path or comment: ${signature}';
  end if;
`;
const wrap = (body, label) => `-- ${label}. Catalog checks only: no planner invocation and no business-row writes.
do $dufynd_release_guard$
declare p pg_proc%rowtype;
begin
  if current_user <> 'postgres' then
    raise exception 'DUFYND release guard: execute as the verified postgres owner';
  end if;
${body}end;
$dufynd_release_guard$;
`;
const oldPlannerCheck = functionCheck('public.plan_dufynd_autonomous_business_work_v1()', baseline.definition_md5);
const newPlannerCheck = functionCheck('public.plan_dufynd_autonomous_business_work_v1()', planner.definition_md5);
const helperCheck = functionCheck('public.read_dufynd_business_source_v1(jsonb)', helper.definition_md5);
const lock = `
  if not pg_try_advisory_xact_lock(hashtext('dufynd-autonomous-business-planner-v1')) then
    raise exception 'DUFYND release guard: planner currently running; transaction aborted';
  end if;
`;
const dependencies = `
  if to_regprocedure('public.get_dufynd_next_autonomous_action()') is null or
     to_regprocedure('public.read_dufynd_first_money_runtime()') is null then
    raise exception 'DUFYND release guard: required planner/runtime function missing';
  end if;
  -- Parse all referenced relation fields without evaluating the business functions.
  perform key,category,value,priority,last_verified_at from public.dufynd_master_status limit 0;
  perform id,content_id,platform from public.dufynd_content_assets limit 0;
  perform asset_id,revision_fingerprint,evidence from public.dufynd_content_workflows limit 0;
  perform task_id,domain,title,instruction,status,priority,budget_class,resource_scope,
    durability_policy,durable_payload,forbidden_actions from public.dufynd_autonomy_tasks limit 0;
`;
const preflight = wrap(lock + oldPlannerCheck + `
  -- A known inert helper may remain after the documented function-only rollback.
  if to_regprocedure('public.read_dufynd_business_source_v1(jsonb)') is not null then
${helperCheck}  end if;
` + dependencies, 'Preflight; include inside the same deployment transaction');
const postflight = wrap(newPlannerCheck + helperCheck, 'Postflight for the exact reviewed migration');
const rollbackPreflight = wrap(lock + newPlannerCheck + helperCheck, 'Rollback preflight');
const rollbackPostflight = wrap(oldPlannerCheck + helperCheck, 'Rollback postflight; helper remains private and inert');
const txHeader = `-- PREPARED ONLY. Production execution requires separate concrete Owner GO.
-- Run the complete file in one database session with stop-on-error enabled.
begin;
set local lock_timeout='2s';
set local statement_timeout='30s';
`;
write('preflight.sql', preflight);
write('postflight.sql', postflight);
write('apply.sql', txHeader + preflight + '\n-- BEGIN EXACT REVIEWED MIGRATION\n' + migration +
  '-- END EXACT REVIEWED MIGRATION\n\n' + postflight + '\ncommit;\n');
write('rollback.sql', txHeader + rollbackPreflight + '\n' + read('baseline-planner.sql') +
  '\n' + rollbackPostflight + '\ncommit;\n');
// Separately tracked migrations can use these transaction bodies. The approved
// migration runner must keep one transaction and record the intended version.
const runnerTimeouts = "set local lock_timeout='2s';\nset local statement_timeout='30s';\n";
const atomicBody = sql => `-- One PostgreSQL statement: guards and DDL succeed or roll back together.\n` +
  `do $dufynd_atomic_migration$\nbegin\n  execute $dufynd_migration_payload$\n` +
  runnerTimeouts + sql + `\n$dufynd_migration_payload$;\nend;\n$dufynd_atomic_migration$;\n`;
write('apply-body.sql', atomicBody(preflight + '\n' + migration + '\n' + postflight));
write('rollback-body.sql', atomicBody(rollbackPreflight + '\n' + read('baseline-planner.sql') + '\n' + rollbackPostflight));
const files = ['production-baseline.json','baseline-planner.sql','expected-functions.json',
  'production-migration-history.json','preflight.sql','postflight.sql','apply.sql','rollback.sql',
  'apply-body.sql','rollback-body.sql','README.md','test-release-packet.cjs',
  'test-migration-body.cjs','release-rehearsal.json','migration-body-rehearsal.json',
  'build-packet.cjs','extract-local-functions.cjs'];
write('manifest.json', JSON.stringify({
  project_id:'bqsdxaagklpkxioaqdqa', checked_at:baseline.checked_at,
  production_commit:'7b793cf7ce1223967e66d768fcb7930ecdfc0e40',
  reviewed_pr:839, reviewed_commit:'e571331222c7649a49c2758de432d6f21d6b9825',
  native_ci_run:40303294857, native_ci_commit:'3d272051c2ece547e3a5cff8f9b9bc76d61f8600',
  migration_path:migrationPath, migration_sha256:sha256(migration),
  before_planner_md5:baseline.definition_md5, after_planner_md5:planner.definition_md5,
  helper_md5:helper.definition_md5,
  production_execution:false, history_policy:'After separate Owner GO, apply exactly apply-body.sql through Supabase apply_migration; read back and record its generated history version and map it to the unchanged source-file hash. Rollback is another separately approved tracked apply_migration using rollback-body.sql. No generic db push, history repair, synthetic migrations or direct history-table writes.',
  files:Object.fromEntries(files.map(name=>[name,sha256(read(name))]))
},null,2)+'\n');
console.log('Built guarded apply/rollback payloads; no database connection opened.');
