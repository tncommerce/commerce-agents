import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import QualifiedProductPage from '@/components/QualifiedProductPage';
import { RELEASE_PILOTS, PILOT_REVIEW_ENABLED } from '@/lib/releasePilots';
export const dynamicParams = false;
export function generateStaticParams() {return PILOT_REVIEW_ENABLED ? RELEASE_PILOTS.map(p=>({slug:p.slug})) : [{slug:'disabled'}];}
export async function generateMetadata({params}:{params:Promise<{slug:string}>}):Promise<Metadata> {
 const {slug}=await params;const p=RELEASE_PILOTS.find(p=>p.slug===slug);
 return {title:p?.seo.title||'Duftprofil – Designprüfung',description:p?.seo.description,robots:{index:false,follow:false},alternates:{canonical:null},openGraph:{title:p?.seo.title,description:p?.seo.description}};
}
export default async function ReviewProductPage({params}:{params:Promise<{slug:string}>}) {
 const {slug}=await params;const pilot=RELEASE_PILOTS.find(p=>p.slug===slug);
 if(!PILOT_REVIEW_ENABLED||!pilot) notFound();
 return <QualifiedProductPage pilot={pilot} profiles={RELEASE_PILOTS}/>;
}
