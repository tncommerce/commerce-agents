export function publicShareUrl(url: string): string {
  const target = new URL(url);
  target.searchParams.delete("sid");
  return target.toString();
}
