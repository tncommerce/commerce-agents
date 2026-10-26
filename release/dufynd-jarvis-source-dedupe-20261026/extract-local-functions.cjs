// Offline helper: read PostgreSQL-normalized definitions from the exact migration.
const { PGlite } = require('@electric-sql/pglite');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const read = (p) => fs.readFileSync(path.join(root, p), 'utf8');
(async () => {
  const db = new PGlite();
  try {
    await db.exec(read('tests/dufynd_budget_schema_fixture.sql'));
    await db.exec(`create table public.dufynd_content_assets(id text,content_id text,platform text);
      create table public.dufynd_content_workflows(asset_id text,revision_fingerprint text,evidence jsonb);`);
    await db.exec(read('supabase/migrations/20261026122726_jarvis_business_source_dedupe.sql'));
    const result = await db.query(`select p.oid::regprocedure::text as name,
      md5(pg_get_functiondef(p.oid)) as definition_md5, pg_get_functiondef(p.oid) as definition,
      pg_get_userbyid(p.proowner) as owner,p.proacl::text as acl
      from pg_proc p where p.oid in ('public.plan_dufynd_autonomous_business_work_v1()'::regprocedure,
        'public.read_dufynd_business_source_v1(jsonb)'::regprocedure) order by 1`);
    fs.writeFileSync(path.join(__dirname, 'expected-functions.json'), JSON.stringify(result.rows, null, 2)+'\n');
    console.log(JSON.stringify(result.rows.map(({name,definition_md5,owner,acl})=>({name,definition_md5,owner,acl})),null,2));
  } finally { await db.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
