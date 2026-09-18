// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { type AgentEvent, formatMoney, StoreShell, type StoreView, useAgentTurn, useSession } from "web-shared";
import CartPanel from "@/components/CartPanel";
import Chat from "@/components/Chat";
import HomeView from "@/components/views/HomeView";
import { api, UNREACHABLE } from "@/lib/api";
import { advisorStartPrompt } from "@/lib/advisorStarts";
import { trackAnalyticsEvent } from "@/lib/analytics";
import type { CartPayload } from "@/lib/types";

type View = "assistant";

const ASSISTANT = "SCENTAI Advisor";

function Wordmark() {
  return (
    <span className="flex items-center gap-2.5 pr-1">
      <span aria-hidden className="grid h-[30px] w-[30px] place-items-center rounded-lg bg-(--ink) text-[15px] font-bold text-(--surface)">
        S
      </span>
      <span className="text-[17px] font-bold tracking-[-0.02em] text-(--ink)">SCENTAI</span>
    </span>
  );
}

export default function StorefrontPage() {
  const session = useSession(api);
  const [view, setView] = useState<View>("assistant");
  const [cart, setCart] = useState<CartPayload | null>(null);
  // A staged checkout owns the panel's primary action until the cart changes again.
  const [checkoutStaged, setCheckoutStaged] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const analyticsSessionRef = useRef<string | null>(null);
  const consultationTrackedRef = useRef(false);
  const guidedStartRef = useRef<string | null>(null);

  const handleCartUpdate = useCallback((next: CartPayload) => {
    setCart(next);
    setCheckoutStaged(false);
  }, []);

  const onEvent = useCallback(
    (event: AgentEvent) => {
      if (event.type === "cart_update") handleCartUpdate(event.data.cart as CartPayload);
      else if (event.type === "ui" && event.data.component === "checkout") setCheckoutStaged(true);
    },
    [handleCartUpdate],
  );

  const chat = useAgentTurn(api, { ...session, unreachable: UNREACHABLE, onEvent });

  useEffect(() => {
    if (!session.sessionId || analyticsSessionRef.current === session.sessionId) return;
    analyticsSessionRef.current = session.sessionId;
    consultationTrackedRef.current = false;
    void trackAnalyticsEvent("page_view", { source: "storefront" });
  }, [session.sessionId]);
  useEffect(() => {
    if (
      !session.sessionId ||
      chat.busy ||
      chat.turnCount > 0 ||
      guidedStartRef.current
    ) {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const startKey = params.get("start");
    const prompt = advisorStartPrompt(startKey);

    if (!startKey || !prompt) return;

    guidedStartRef.current = startKey;
    window.history.replaceState(
      {},
      "",
      window.location.pathname,
    );
    void chat.send(prompt);
  }, [
    chat.busy,
    chat.send,
    chat.turnCount,
    session.sessionId,
  ]);


  useEffect(() => {
    if (!session.sessionId || chat.turnCount < 1 || consultationTrackedRef.current) return;
    consultationTrackedRef.current = true;
    void trackAnalyticsEvent("consultation_start", {
      source: guidedStartRef.current
        ? `advisor_start_${guidedStartRef.current}`
        : "advisor",
    });
  }, [chat.turnCount, session.sessionId]);

  useEffect(() => {
    if (session.sessionId) void api.fetchCart<CartPayload>().then((next) => next && setCart(next));
  }, [session.sessionId]);

  const views: StoreView<View>[] = [
    { id: "assistant", label: "Beratung", icon: "spark" },
  ];
  const shopper = session.shopper ?? { name: "Guest" };
  const count = cart?.item_count ?? 0;

  return (
    <StoreShell
      minimal
      brand={<Wordmark />}
      views={views}
      view={view}
      onViewChange={setView}
      chat={chat}
      api={api}
      assistantName={ASSISTANT}
      shopper={shopper}
      bag={{ label: "Warenkorb", count, noun: "Artikel", figure: count ? formatMoney(cart?.subtotal ?? 0, cart?.currency) : null }}
      panel={<CartPanel cart={cart} checkoutStaged={checkoutStaged} />}
      panelOpen={panelOpen}
      onPanelOpenChange={setPanelOpen}
      placeholder="Beschreibe deinen Wunsch, einen Duft oder dein Budget…"
    >
      {/* The conversation stays mounted under the other view so its cards keep their state. */}
      <div className={view === "assistant" ? "h-full" : "hidden"}>
        <Chat chat={chat} onCartUpdate={handleCartUpdate} home={<HomeView shopperName={shopper.name} />} />
      </div>
    </StoreShell>
  );
}
