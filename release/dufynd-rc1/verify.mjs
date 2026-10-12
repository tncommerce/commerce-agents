import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {readFileSync,writeFileSync,mkdirSync,existsSync,readdirSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const here=path.dirname(fileURLToPath(import.meta.url));
const repo=path.resolve(here,'../..');
const [mode,destination,output]=process.argv.slice(2);
assert.ok(['prepare','export','rollback'].includes(mode));
assert.ok(destination&&output,'Explicit disposable candidate and evidence directories required');
const candidate=path.resolve(destination), evidence=path.resolve(output);
assert.ok(candidate!==repo&&!candidate.startsWith(repo+'/'),'Candidate must be outside development checkout');
const m=JSON.parse(readFileSync(path.join(here,'manifest.json')));
const expected=['examples/retail/storefront-web/app/duft/[slug]/page.tsx','examples/retail/storefront-web/app/duft/[slug]/first-money.module.css','examples/retail/storefront-web/components/FragranceOffers.tsx'].sort();
assert.equal(m.base_commit,'86d58bee958cade3ef372ddeaa6d9cf5baaa003e');
assert.equal(m.publication_authorized,false);
assert.deepEqual([...m.files].sort(),expected);
const patch=readFileSync(path.join(here,'candidate.patch'));
assert.equal(createHash('sha256').update(patch).digest('hex'),m.patch_sha256);
const git=(args,cwd=candidate)=>execFileSync('git',args,{cwd,encoding:'utf8'}).trim();
const list=s=>s?s.split('\n').sort():[];
mkdirSync(evidence,{recursive:true});
if(mode==='prepare') {
 assert.ok(!existsSync(candidate),'Refuse existing candidate directory');
 git(['worktree','add','--detach',candidate,m.base_commit],repo);
 assert.equal(git(['rev-parse','HEAD']),m.base_commit);
 assert.equal(git(['rev-parse','HEAD^{tree}']),m.base_tree);
 git(['apply','--check',path.join(here,'candidate.patch')]);
 git(['apply',path.join(here,'candidate.patch')]);
 git(['add','--',...m.files]);
 assert.deepEqual(list(git(['diff','--cached','--name-only'])),expected);
 assert.equal(git(['write-tree']),m.candidate_tree);
 writeFileSync(path.join(evidence,'source.json'),JSON.stringify({...m,patch_applied:true,branch_created:false},null,2));
} else if(mode==='export') {
 assert.equal(git(['write-tree']),m.candidate_tree);
 assert.equal(git(['diff','--name-only']), '','Tracked source changed during build');
 const out=path.join(candidate,'examples/retail/storefront-web/out');
 assert.ok(existsSync(path.join(out,'duft/rabanne-1-million.html')));
 for(const name of ['review','__review-photos']) assert.equal(existsSync(path.join(out,name)),false);
 const walk=d=>readdirSync(d,{withFileTypes:true}).flatMap(x=>x.isDirectory()?walk(path.join(d,x.name)):[path.join(d,x.name)]);
 const files=walk(out);
 const privatePhotos=JSON.parse(readFileSync(path.join(repo,'examples/retail/data/dufynd_photo_integration_review.json'))).items;
 const privatePilots=JSON.parse(readFileSync(path.join(repo,'examples/retail/data/dufynd_release_pilots.json'))).pilots;
 for(const p of privatePilots) assert.equal(existsSync(path.join(out,'duft',p.slug+'.html')),false,`Private profile exported: ${p.slug}`);
 for(const f of files.filter(f=>/\.(html|txt|js|json)$/.test(f))) {
  const s=readFileSync(f,'utf8');
  assert.ok(!/qa-rc1-fixture|qa-rc1-session|recorded_public_api_observation_not_current_quote|data-photo-review-boundary/.test(s),`QA/review data leaked: ${f}`);
  for(const p of privatePhotos) assert.ok(!s.includes(p.image_sha256)&&!s.includes(p.image_url),`Private photo leaked: ${f}`);
 }
 const html=readFileSync(path.join(out,'duft/rabanne-1-million.html'),'utf8');
 assert.ok(!html.includes('Preisreferenz'));
 assert.ok(html.includes('data-first-money-landing="true"'));
 writeFileSync(path.join(evidence,'export.json'),JSON.stringify({candidate_tree:m.candidate_tree,public_files:files.length,private_profiles_absent:privatePilots.length,private_photos_absent:privatePhotos.length,qa_payload_absent:true,source_unchanged:true},null,2));
} else {
 assert.equal(git(['write-tree']),m.candidate_tree);
 git(['apply','--reverse','--check',path.join(here,'candidate.patch')]);
 git(['apply','--reverse',path.join(here,'candidate.patch')]);
 git(['add','--',...m.files]);
 assert.equal(git(['write-tree']),m.base_tree);
 assert.equal(git(['diff','--name-only']),'');
 assert.equal(git(['diff','--cached','--name-only']),'');
 writeFileSync(path.join(evidence,'rollback.json'),JSON.stringify({restored_tree:git(['write-tree']),expected_base_tree:m.base_tree,exact_match:true,working_tree_restored:true,no_commit_or_ref_created:true},null,2));
 // Restore the already verified candidate for artifact inspection; still detached.
 git(['apply',path.join(here,'candidate.patch')]);git(['add','--',...m.files]);
 assert.equal(git(['write-tree']),m.candidate_tree);
}
console.log(JSON.stringify({mode,status:'passed',candidate_tree:m.candidate_tree}));
