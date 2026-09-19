export const GUIDED_START_STORAGE_KEY =
  "scentai_guided_start_v1";

export const GUIDED_PROMPT_STORAGE_KEY =
  "scentai_guided_prompt_v1";

export const MAX_GUIDED_PROMPT_LENGTH = 2400;

export const ADVISOR_STARTS = {
  summer:
    "Ich suche einen frischen Sommerduft unter 60 €.",
  date:
    "Ich suche einen eleganten Duft für ein Date unter 100 €.",
  alternative:
    "Finde mir eine gute Alternative zu Louis Vuitton Imagination.",
  performance:
    "Ich suche einen Duft mit starker Haltbarkeit und Ausstrahlung.",
  gift:
    "Hilf mir, ein Parfum als Geschenk zu finden. Stelle mir zuerst die wichtigsten Fragen zu Person, Budget und Vorlieben.",
  office:
    "Ich suche einen angenehmen Büroduft, der gepflegt wirkt und nicht zu aufdringlich ist.",
  signature:
    "Hilf mir, einen Signature-Duft zu finden, der wirklich zu mir passt. Stelle mir dafür zuerst ein paar gezielte Fragen.",
  collection:
    "Hilf mir, meine bestehende Duftsammlung sinnvoll zu ergänzen. Frage mich zuerst nach Anlass, Budget und dem gewünschten Unterschied zu meinen vorhandenen Düften.",
} as const;

export type AdvisorStartKey = keyof typeof ADVISOR_STARTS;

export function advisorStartPrompt(
  value: string | null,
): string | null {
  if (!value) return null;
  return Object.prototype.hasOwnProperty.call(
    ADVISOR_STARTS,
    value,
  )
    ? ADVISOR_STARTS[value as AdvisorStartKey]
    : null;
}

export function advisorStartHref(
  key: AdvisorStartKey,
): string {
  return `/?start=${encodeURIComponent(key)}`;
}


export function normalizeGuidedPrompt(
  value: string | null,
): string | null {
  if (!value) return null;

  const normalized = value
    .normalize("NFKC")
    .replace(/\s+/g, " ")
    .trim();

  if (!normalized) return null;

  return normalized.slice(0, MAX_GUIDED_PROMPT_LENGTH);
}
