// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import type { ReactNode } from "react";
import { ActivityLine, type AgentTurn, type AssistantChatItem, Chat as ChatShell } from "web-shared";
import GenerativeBlock from "./generative";

const WIDE = new Set(["comparison", "plan"]);

function scentaiErrorText() {
  return "DUFYND ist gerade kurz nicht erreichbar. Bitte versuche es in einem Moment erneut.";
}

/** Shimmers where the carousel will land while a search runs. */
function Pending({ item }: { item: AssistantChatItem }) {
  const searching = item.tools.includes("search_products") && !item.segments.some((s) => s.type === "ui");
  if (!searching) return <ActivityLine item={item} />;
  return (
    <section role="status" className="rounded-2xl border border-(--line) bg-(--card) p-3 shadow-(--shadow-sm)">
      <div className="mb-3 animate-pulse text-[15px] text-(--ink-soft)">{item.activity ?? "Ich suche passende Düfte…"}</div>
      <div className="flex gap-3 overflow-hidden pb-1">
        {[0, 1, 2, 3].map((slot) => (
          <div key={slot} className="ac-skeleton h-[150px] w-48 shrink-0 rounded-xl" />
        ))}
      </div>
    </section>
  );
}

export default function Chat({
  chat,
  home,
}: {
  chat: AgentTurn;
  home: ReactNode;
}) {
  return (
    <ChatShell
      chat={chat}
      home={home}
      wide={WIDE}
      maxWidthClass="max-w-[1080px]"
      errorText={scentaiErrorText}
      renderPending={(item) => <Pending item={item} />}
      renderBlock={(segment) => (
        <GenerativeBlock
          block={segment.block}
          status={segment.status}
        />
      )}
    />
  );
}
