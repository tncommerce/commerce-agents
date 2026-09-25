/** Historical market observations; these are not live merchant offers. */
export function formatPriceReference(
  amount: number | null,
  checkedAt: string | null,
): string {
  if (amount == null || !Number.isFinite(amount) || !checkedAt) return "–";

  const date = new Date(`${checkedAt}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(checkedAt) ||
      Number.isNaN(date.getTime()) ||
      date.toISOString().slice(0, 10) !== checkedAt) return "–";

  const price = new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
  }).format(amount);
  const day = date.toLocaleDateString("de-DE", { timeZone: "UTC" });
  return `${price} · Stand ${day}`;
}
