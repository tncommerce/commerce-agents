import {readFileSync, writeFileSync, mkdirSync, rmSync} from 'node:fs';
import {createHash} from 'node:crypto';
export async function preparePhotoReview({enabled=process.env.DUFYND_CATALOG_REVIEW==='1', destination=new URL('../public/__review-photos/',import.meta.url), manifest=JSON.parse(readFileSync(new URL('../../data/dufynd_photo_integration_review.json',import.meta.url),'utf8')), fetchSource=fetch}={}) {
 rmSync(destination,{recursive:true,force:true});
 if (!enabled) return;
 try {
  mkdirSync(destination, {recursive:true});
  for (const item of manifest.items) {
    const source = new URL(item.image_url);
    if(source.protocol !== 'https:' || source.hostname !== 'www.topparfuemerie.de' || !source.pathname.startsWith('/media/catalog/product/') ||
       item.owner_visual_approved !== true || item.exact_variant_verified !== true || item.publication_authorized !== false || item.offer_activation_authorized !== false ||
       item.merchant_id !== 'top-parfuemerie' || item.source_advertiser_id !== '31081' || item.source_feed_id !== '91379' ||
       item.rights_basis_id !== 'awin_top_parfuemerie_feed_materials_20260928' || !/^\d+$/.test(item.merchant_product_id) ||
       item.placement !== 'top_parfuemerie_private_review_only' || !/^[a-f0-9]{64}$/.test(item.image_sha256)) throw Error('Invalid private photo source');
    const response = await fetchSource(source, {signal:AbortSignal.timeout(30000), redirect:'error'});
    if(!response.ok) throw Error(`Photo source unavailable: ${item.merchant_product_id}`);
    const bytes = Buffer.from(await response.arrayBuffer());
    if(createHash('sha256').update(bytes).digest('hex') !== item.image_sha256) throw Error(`Photo bytes changed: ${item.merchant_product_id}; new review required`);
    writeFileSync(new URL(`${item.merchant_product_id}-${item.image_sha256}.png`, destination), bytes);
  }
  console.log(`${manifest.items.length} unchanged, hash-bound photos prepared for merchant-only private review.`);
 } catch(error) {
   rmSync(destination,{recursive:true,force:true});
   throw error;
 }
}
