// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

import { formatMoney } from "web-shared";
import type { ComparisonPayload } from "@/lib/types";
import { ProductImage, ProductTitle, ProductRating } from "../ProductTile";

const RECOMMENDED_LABEL = "Empfehlung";

function TermRow({ sign, text }: { sign: "+" | "−"; text: string }) {
  return (
    <div className="grid grid-cols-[1.1rem_1fr] gap-1 text-[13px] leading-relaxed text-(--ink)">
      <span
        aria-hidden
        className={sign === "+" ? "font-semibold text-(--ok)" : "font-semibold text-(--ink-soft)"}
      >
        {sign}
      </span>
      <span>{text}</span>
    </div>
  );
}

export default function ComparisonGrid({
  payload,
  partial,
}: {
  payload: ComparisonPayload;
  partial?: boolean;
}) {
  const entries = payload.entries ?? [];
  const delta = payload.price_delta;
  const hasDecisionDetails = entries.some(
    (entry) => entry.best_for || (entry.pros?.length ?? 0) > 0 || (entry.cons?.length ?? 0) > 0,
  );

  return (
    <section className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm)">
      {payload.title ? (
        <h3 className="mb-3 text-[15px] font-semibold text-(--ink)">{payload.title}</h3>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        {entries.map((entry) => {
          const recommended = payload.recommended_product_id === entry.product_id;
          return (
            <div
              key={entry.product_id}
              className={`rounded-xl border p-4 ${
                recommended ? "border-(--accent) bg-(--accent-soft)/60" : "border-(--line)"
              }`}
            >
              <div className="flex items-center gap-3">
                <ProductImage product={entry.product} className="h-16 w-16 shrink-0 rounded-lg" />
                <div className="min-w-0">
                  {recommended ? (
                    <div className="mb-0.5 text-[11px] font-bold uppercase tracking-wide text-(--ink)">
                      {RECOMMENDED_LABEL}
                    </div>
                  ) : null}
                  <ProductTitle
                    title={entry.product.title}
                    className="line-clamp-2 text-sm font-medium leading-snug"
                  />
                  <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm">
                    <span className="font-semibold">{formatMoney(entry.product.price)}</span>
                    <ProductRating product={entry.product} />
                  </div>
                </div>
              </div>
            </div>
          );
        })}
        {partial ? <div className="ac-skeleton h-28 rounded-xl" /> : null}
      </div>

      {hasDecisionDetails ? (
        <div className="mt-4 border-t border-(--line) pt-4">
          <div className="mb-3 text-[13px] font-semibold text-(--ink)">Entscheidungshilfe</div>
          <div className="grid gap-3 sm:grid-cols-2">
            {entries.map((entry) => {
              const recommended = payload.recommended_product_id === entry.product_id;
              const pros = entry.pros ?? [];
              const cons = entry.cons ?? [];
              return (
                <div
                  key={`${entry.product_id}-details`}
                  className="rounded-xl bg-(--well) p-3"
                >
                  <div className="mb-2 flex items-start justify-between gap-2">
                    <div className="min-w-0 text-[13px] font-semibold text-(--ink)">
                      {entry.product.brand ? `${entry.product.brand} · ` : ""}
                      <span className="font-medium">{entry.product.title}</span>
                    </div>
                    {recommended ? (
                      <span className="shrink-0 rounded-full border border-(--accent) bg-(--accent-soft) px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-(--ink)">
                        Empfehlung
                      </span>
                    ) : null}
                  </div>

                  {entry.best_for ? (
                    <div className="mb-3 rounded-lg border border-(--line) bg-(--card) px-2.5 py-2 text-[13px] leading-relaxed text-(--ink)">
                      <span className="font-semibold">Ideal für:</span> {entry.best_for}
                    </div>
                  ) : null}

                  {pros.length ? (
                    <div className="space-y-1.5">
                      <div className="text-[11px] font-bold uppercase tracking-wide text-(--ink-soft)">
                        Stärken
                      </div>
                      {pros.map((pro) => (
                        <TermRow key={pro} sign="+" text={pro} />
                      ))}
                    </div>
                  ) : null}

                  {cons.length ? (
                    <div className={`${pros.length ? "mt-3" : ""} space-y-1.5`}>
                      <div className="text-[11px] font-bold uppercase tracking-wide text-(--ink-soft)">
                        Abwägungen
                      </div>
                      {cons.map((con) => (
                        <TermRow key={con} sign="−" text={con} />
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {delta ? (
        <p className="mt-4 text-[13px] text-(--ink)">
          Preisunterschied:{" "}
          <span className="font-semibold">{formatMoney(delta.amount)}</span>{" "}
          <span className="text-(--ink-soft)">
            ({formatMoney(delta.low_price)} vs. {formatMoney(delta.high_price)})
          </span>
        </p>
      ) : null}

      {payload.dimensions?.length ? (
        <p className="mt-2 text-xs text-(--ink-soft)/80">
          Verglichen nach: {payload.dimensions.join(" · ")}
        </p>
      ) : null}
    </section>
  );
}
