/**
 * A deliberate playful style exercise, not a factual scent recommendation.
 * Keep labels separate from catalogue truth and do not invent SKU/price data.
 */
export type DuelChoice = "a" | "b";
export type DuelRound = {
  id: string;
  eyebrow: string;
  question: string;
  options: readonly [
    { label: string; detail: string; vibe: string; warmth: number; presence: number },
    { label: string; detail: string; vibe: string; warmth: number; presence: number },
  ];
};

export const DUEL_ROUNDS: readonly DuelRound[] = [
  {
    id: "first-impression",
    eyebrow: "01 / Erste Intuition",
    question: "Du riechst lieber …",
    options: [
      { label: "Frisch. Klar.", detail: "Zitrus, Luft, grüne Ideen", vibe: "A / CLEAR", warmth: -2, presence: 0 },
      { label: "Warm. Tief.", detail: "Weiche Hölzer, sanfte Würze", vibe: "B / WARM", warmth: 2, presence: 0 },
    ],
  },
  {
    id: "presence",
    eyebrow: "02 / Deine Präsenz",
    question: "Lieber Understatement oder Statement?",
    options: [
      { label: "Understatement.", detail: "Unaufgeregt, ganz dein Ding", vibe: "A / SOFT", warmth: 0, presence: -2 },
      { label: "Statement.", detail: "Eine klare Duftentscheidung", vibe: "B / BOLD", warmth: 0, presence: 2 },
    ],
  },
  {
    id: "occasion",
    eyebrow: "03 / Der Moment",
    question: "Dein Duft-Moment ist …",
    options: [
      { label: "Jeden Tag.", detail: "Dein unkomplizierter Begleiter", vibe: "A / DAY", warmth: -1, presence: -1 },
      { label: "Später Abend.", detail: "Ein besonderer Auftritt", vibe: "B / NIGHT", warmth: 1, presence: 1 },
    ],
  },
  {
    id: "instinct",
    eyebrow: "04 / Bauchgefühl",
    question: "Welches Wort gewinnt?",
    options: [
      { label: "Zitrus.", detail: "Hell, lebendig, leicht", vibe: "A / BRIGHT", warmth: -1, presence: 0 },
      { label: "Gewürz.", detail: "Markant, trocken, holzig", vibe: "B / SPICE", warmth: 1, presence: 0 },
    ],
  },
] as const;

export type DuelIdentity = "clean" | "sunset" | "electric" | "afterdark";
export type DuelOutcome = {
  id: DuelIdentity;
  index: string;
  name: string;
  kicker: string;
  description: string;
  tags: readonly string[];
  advisorSeed: string;
};

export const DUEL_OUTCOMES: Record<DuelIdentity, DuelOutcome> = {
  clean: {
    id: "clean",
    index: "01",
    name: "The Clean Edit",
    kicker: "Leise. Klar. Selbstverständlich.",
    description: "Du magst es frisch und zurückhaltend. Du willst einen Duftstil, der sich leicht in deinen Alltag einfügt.",
    tags: ["frisch", "dezent", "Alltag"],
    advisorSeed: "Ich bevorzuge eher frische, klare und zurückhaltende Duftprofile für den Alltag.",
  },
  sunset: {
    id: "sunset",
    index: "02",
    name: "Golden Hour",
    kicker: "Warm. Ruhig. Charaktervoll.",
    description: "Warme, eher sanfte Duftideen sprechen dich an. Du willst Details statt Lautstärke.",
    tags: ["warm", "weich", "unaufgeregt"],
    advisorSeed: "Ich bevorzuge warme und eher zurückhaltende Duftprofile mit weichem Charakter.",
  },
  electric: {
    id: "electric",
    index: "03",
    name: "The Wildcard",
    kicker: "Frisch. Mutig. Unverwechselbar.",
    description: "Du liebst Klarheit, aber auch einen markanten Auftritt. Dein Duftstil darf Gegensätze haben.",
    tags: ["frisch", "markant", "kontrastreich"],
    advisorSeed: "Ich bevorzuge frische, klare, aber markantere Duftprofile mit auffälligem Charakter.",
  },
  afterdark: {
    id: "afterdark",
    index: "04",
    name: "After Dark",
    kicker: "Würzig. Ausdrucksstark. Eigen.",
    description: "Warme und kräftigere Duftideen interessieren dich. Du suchst einen bewusst gewählten Duftstil für besondere Momente.",
    tags: ["warm", "würzig", "Statement"],
    advisorSeed: "Ich bevorzuge warme, würzige und eher markante Duftprofile, besonders für den Abend.",
  },
};

export function getDuelOutcome(answers: readonly DuelChoice[]): DuelOutcome | null {
  if (answers.length !== DUEL_ROUNDS.length) return null;
  let warmth = 0;
  let presence = 0;
  for (let i = 0; i < DUEL_ROUNDS.length; i += 1) {
    const choice = answers[i];
    if (choice !== "a" && choice !== "b") return null;
    const option = DUEL_ROUNDS[i].options[choice === "a" ? 0 : 1];
    warmth += option.warmth;
    presence += option.presence;
  }
  if (warmth > 0) return presence > 0 ? DUEL_OUTCOMES.afterdark : DUEL_OUTCOMES.sunset;
  return presence > 0 ? DUEL_OUTCOMES.electric : DUEL_OUTCOMES.clean;
}

export function getDuelAdvisorPrompt(answers: readonly DuelChoice[]): string | null {
  const outcome = getDuelOutcome(answers);
  if (!outcome) return null;
  return `Ich habe im DUFYND Duft-Duell den Stil „${outcome.name}“ gewählt. ${outcome.advisorSeed} Bitte frag mich noch nach Budget und Anlass und empfehle erst dann passende, tatsächlich im DUFYND-Katalog dokumentierte Düfte. Erfinde keine Preise, Verfügbarkeiten oder Duftnoten.`;
}
