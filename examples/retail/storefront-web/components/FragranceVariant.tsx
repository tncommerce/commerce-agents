/** The exact catalog variant, never inferred from a photograph or an offer. */
export default function FragranceVariant({ concentration, volume }: {
  concentration: string;
  volume: number;
}) {
  return (
    <dl className="dufynd-product-variant" aria-label="Exakte Duftvariante">
      <div><dt>Konzentration</dt><dd>{concentration}</dd></div>
      <div><dt>Größe</dt><dd>{volume} ml</dd></div>
    </dl>
  );
}
