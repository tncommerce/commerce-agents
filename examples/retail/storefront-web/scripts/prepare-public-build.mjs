import {rmSync} from 'node:fs';
// These are disposable build outputs, never source data. An incremental export
// can retain an unreferenced old chunk containing withdrawn community data.
for(const name of ['.next','out']) rmSync(new URL(`../${name}`,import.meta.url),{recursive:true,force:true});
console.log('Clean public build: stale browser chunks and previous review exports removed.');
