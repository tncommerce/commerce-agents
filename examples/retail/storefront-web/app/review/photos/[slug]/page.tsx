import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import FragranceDetailPage from '@/components/FragranceDetailPage';
import { PHOTO_REVIEW_ITEMS } from '@/lib/photoIntegrationReview';
export const dynamicParams = false;
export const metadata: Metadata = {title:'Originalfoto · top Parfümerie · Designprüfung',robots:{index:false,follow:false},alternates:{canonical:null}};
export function generateStaticParams() {
  return PHOTO_REVIEW_ITEMS.length ? PHOTO_REVIEW_ITEMS.map(p=>({slug:p.slug})) : [{slug:'disabled'}];
}
export default async function PhotoReviewPage({params}:{params:Promise<{slug:string}>}) {
  const {slug}=await params;
  if(!PHOTO_REVIEW_ITEMS.some(p=>p.slug===slug)) notFound();
  return <FragranceDetailPage params={params} merchantPhotoReview />;
}
