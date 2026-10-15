import FragranceDetailPage, { type PageProps } from '@/components/FragranceDetailPage';
export { generateMetadata, generateStaticParams } from '@/components/FragranceDetailPage';
export const dynamicParams = false;
export default function FragrancePage(props: PageProps) {
  return <FragranceDetailPage params={props.params} />;
}
