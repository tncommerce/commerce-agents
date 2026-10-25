// Optional local real-Postgres/WASM test transport. No network or production DB.
// CI uses PostgreSQL 17 + psycopg instead; this is not a production runtime.
import { createInterface } from 'node:readline';
const { PGlite } = await import(process.env.DUFYND_PGLITE_MODULE);
const db = new PGlite();
for await (const line of createInterface({ input: process.stdin })) {
  try {
    const request = JSON.parse(line);
    const result = request.exec ? await db.exec(request.sql)
      : await db.query(request.sql, request.params || []);
    process.stdout.write(JSON.stringify({ result }) + '\n');
  } catch (error) {
    process.stdout.write(JSON.stringify({ error: error.message }) + '\n');
  }
}
await db.close();
