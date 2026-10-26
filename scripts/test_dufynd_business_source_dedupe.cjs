// Offline PostgreSQL-WASM regression. No network, production DSN or live data.
// Install @electric-sql/pglite@0.3.14 in a temporary prefix and set NODE_PATH
// to that prefix's node_modules. Native CI uses the same SQL assertions.
const { PGlite } = require('@electric-sql/pglite');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

(async () => {
  const db = new PGlite();
  try {
    await db.exec(read('tests/dufynd_budget_schema_fixture.sql'));
    await db.exec(read('supabase/migrations/20261002064614_dufynd_supervisor_v2_phase1.sql')
      .split('-- No model and no paid runner:')[0]);
    // Remaining isolated fixture fields match the existing budget/content
    // PostgreSQL test harness; actual worker/workflow constraints stay active.
    await db.exec(`
      alter table dufynd_autonomy_tasks add column durability_policy text default 'durable',
        add column durable_payload jsonb, add column forbidden_actions jsonb;
      create table dufynd_content_assets(id text primary key, content_id text, platform text,
        status text, version int, uri text, metadata jsonb);
      alter table dufynd_human_decisions add column action_type text, add column title text,
        add column question text, add column decision_token text, add column context jsonb,
        add column updated_at timestamptz;
    `);
    await db.exec(read('supabase/migrations/20261005111923_dufynd_content_workflow_control_plane.sql'));
    const migration = read('supabase/migrations/20261026083433_jarvis_business_source_dedupe.sql');
    await db.exec(migration);
    await db.exec(migration);
    const engine = (await db.query('select version()')).rows[0].version;
    const results = await db.exec(read('tests/sql_dufynd_business_source_dedupe.sql'));
    const cases = results.flatMap((result) => result.rows || []).filter((row) => row.label);
    const remaining = (await db.query("select count(*) from dufynd_master_status where key='jarvis.business_source_dedupe_v1'")).rows[0].count;
    if (cases.length !== 31 || Number(remaining) !== 0) throw new Error('incomplete assertions or rollback');
    console.log(JSON.stringify({ engine, passed: cases.length, checkpointRowsAfterRollback: Number(remaining),
      scope: 'offline PostgreSQL-WASM; not native multi-connection CI', cases }, null, 2));
  } finally {
    await db.close();
  }
})().catch((error) => { console.error(error.message); process.exitCode = 1; });
