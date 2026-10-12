/** Synthetic offline inputs only: no source fetch, staging or release writes. */
import assert from 'node:assert/strict';
import {validateEvidence} from './catalog-growth.mjs';

const sources=[
  ['BDK Parfums','bdkparfums.com'],
  ['Montale','montaleparfums.com'],
  ['Hermès','hermes.com'],
  ['Zadig & Voltaire','zadig-et-voltaire.com'],
];
function fixture(brand,host){
  const row={product_id:'SYNTHETIC-FACT-100',brand,name:'Synthetic source guard',concentration:'Eau de Parfum',volume_ml:100,status:'facts_qualified',source_url:`https://${host}/synthetic`,manufacturer_reference:'synthetic-reference',variant_evidence:'Synthetic test fixture',summary_de:'Synthetic test fixture',notes:{key:['test note']}};
  const packet={checked_at:'2026-10-12',facts_only:true,community_data_included:false,publication_authorized:false,products:[row]};
  return {row,packet,staging:[{...row}]};
}
let cases=0;
for(const [brand,host] of sources){
  for(const acceptedHost of [host,`www.${host}`]){
    const {packet,staging}=fixture(brand,acceptedHost);
    assert.equal(validateEvidence(packet,staging,[]).size,1);cases++;
  }
  for(const wrongHost of [`${host}.example.invalid`,`evil-${host}`,`unreviewed.${host}`]){
    const {packet,staging}=fixture(brand,wrongHost);
    assert.throws(()=>validateEvidence(packet,staging,[]),/missing_manufacturer_evidence/);cases++;
  }
  const wrongBrand=fixture('Unrelated Brand',host);
  assert.throws(()=>validateEvidence(wrongBrand.packet,wrongBrand.staging,[]),/missing_manufacturer_evidence/);cases++;
  for(const [otherBrand,otherHost] of sources.filter(([b])=>b!==brand)){
    const crossed=fixture(brand,otherHost);
    assert.throws(()=>validateEvidence(crossed.packet,crossed.staging,[]),/missing_manufacturer_evidence/,`${brand} must not inherit ${otherBrand}'s source`);cases++;
  }
  const wrongNotes=fixture(brand,host);wrongNotes.row.notes_source_url='https://unrelated.invalid/notes';
  assert.throws(()=>validateEvidence(wrongNotes.packet,wrongNotes.staging,[]),/missing_manufacturer_evidence/);cases++;
  const wrongScheme=fixture(brand,host);wrongScheme.row.source_url=`http://${host}/synthetic`;
  assert.throws(()=>validateEvidence(wrongScheme.packet,wrongScheme.staging,[]),/missing_manufacturer_evidence/);cases++;
  const credentialUrl=fixture(brand,host);credentialUrl.row.source_url=`https://user:password@${host}/synthetic`;
  assert.throws(()=>validateEvidence(credentialUrl.packet,credentialUrl.staging,[]),/missing_manufacturer_evidence/);cases++;
}
console.log(`Manufacturer intake: ${cases} brand/domain/source-bound cases passed; no staging or authorization writes.`);
