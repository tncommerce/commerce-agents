// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import { useEffect, useRef, useState } from "react";
import {
  StoreShell,
  type StoreView,
  useAgentTurn,
  useSession,
} from "web-shared";
import AcquisitionAnalytics from "@/components/AcquisitionAnalytics";
import Chat from "@/components/Chat";
import HomeView from "@/components/views/HomeView";
import { api, UNREACHABLE } from "@/lib/api";
import {
  advisorStartPrompt,
  GUIDED_PROMPT_STORAGE_KEY,
  GUIDED_START_STORAGE_KEY,
  normalizeGuidedPrompt,
} from "@/lib/advisorStarts";
import { trackAnalyticsEvent } from "@/lib/analytics";
import { measurementAllowed, subscribeMeasurement } from "@/lib/measurementConsent";

type View = "assistant";

const ASSISTANT = "DUFYND Advisor";

function Wordmark() {
  return (
    <span className="flex items-center gap-2.5 pr-1">
      <img
        src="/icon.svg"
        alt=""
        aria-hidden
        width={30}
        height={30}
        className="h-[30px] w-[30px] rounded-lg"
      />
      <span className="text-[17px] font-bold tracking-[-0.02em] text-(--ink)">DUFYND</span>
    </span>
  );
}

export default function StorefrontPage() {
  const session = useSession(api, { timeoutMs: 8_000 });
  const [view, setView] = useState<View>("assistant");
  const [panelOpen, setPanelOpen] = useState(false);
  const homepageViewTrackedRef = useRef(false);
  const consultationTrackedRef = useRef(false);
  const guidedStartRef = useRef<string | null>(null);

  const chat = useAgentTurn(api, {
    ...session,
    unreachable: UNREACHABLE,
  });

  useEffect(() => {
    consultationTrackedRef.current = false;
  }, [session.sessionId]);

  useEffect(() => {
    const trackCurrentPage = () => {
      if (!measurementAllowed()) {
        homepageViewTrackedRef.current = false;
        return;
      }
      // Optional first-party measurement must never wait for advisor transport.
      // This existing tracker owns the one consented homepage page_view.
      if (homepageViewTrackedRef.current) return;
      homepageViewTrackedRef.current = true;
      void trackAnalyticsEvent("page_view", { source: "storefront" });
    };
    const unsubscribe = subscribeMeasurement(trackCurrentPage);
    trackCurrentPage();
    return unsubscribe;
  }, []);
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
    const fallbackPrompt = advisorStartPrompt(startKey);

    if (!startKey || !fallbackPrompt) return;

    let confirmedStart: string | null = null;
    let customPrompt: string | null = null;
    try {
      confirmedStart = window.sessionStorage.getItem(
        GUIDED_START_STORAGE_KEY,
      );
      customPrompt = normalizeGuidedPrompt(
        window.sessionStorage.getItem(
          GUIDED_PROMPT_STORAGE_KEY,
        ),
      );
      window.sessionStorage.removeItem(
        GUIDED_START_STORAGE_KEY,
      );
      window.sessionStorage.removeItem(
        GUIDED_PROMPT_STORAGE_KEY,
      );
    } catch {
      confirmedStart = null;
      customPrompt = null;
    }

    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.delete("start");
    window.history.replaceState(
      window.history.state,
      "",
      `${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`,
    );

    if (confirmedStart !== startKey) return;

    guidedStartRef.current = startKey;
    void chat.send(customPrompt || fallbackPrompt);
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

  const views: StoreView<View>[] = [
    { id: "assistant", label: "Beratung", icon: "spark" },
  ];
  const shopper = session.shopper ?? { name: "Guest" };

  return (
    <>
      <AcquisitionAnalytics
        source="storefront"
        trackPageView={false}
      />
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
      bag={{ label: "DUFYND", count: 0, noun: "Artikel" }}
      panel={null}
      panelOpen={panelOpen}
      onPanelOpenChange={setPanelOpen}
      placeholder="Frage an die Duftberatung …"
      composerLabel="Nachricht an DUFYND Advisor"
      hideComposer={chat.items.length === 0}
    >
      {/* The conversation stays mounted under the other view so its cards keep their state. */}
      <div className={view === "assistant" ? "h-full" : "hidden"}>
        <Chat
          chat={chat}
          home={(
            <HomeView
              shopperName={shopper.name}
              sessionSettled={session.settled === true}
            />
          )}
        />
      </div>
      </StoreShell>
    </>
  );
}
