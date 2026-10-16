// Native-browser QA helper. qa=1 and URL parameters never grant optional
// measurement; positive fixtures make an explicit, ordinary UI choice.
export async function chooseMeasurement(page, choice = "granted") {
  const expected = choice === "granted" ? "granted" : "denied";
  const region = page.locator("[data-measurement-choice]").first();
  await region.waitFor({ state: "attached", timeout: 10_000 });
  const current = await region.getAttribute("data-measurement-choice");
  if (current === expected) return;
  if (current === "granted" && expected === "denied") {
    await page.getByRole("button", { name: "Analyse widerrufen", exact: true }).click();
  } else {
    if (current !== "unknown") {
      await page.getByRole("button", { name: "Datenschutz-Einstellungen", exact: true }).click();
    }
    const name = expected === "granted" ? "Analyse erlauben" : "Nur notwendige Funktionen";
    try {
      await page.getByRole("button", { name, exact: true }).click({ timeout: 2_000 });
    } catch (error) {
      // A navigation can expose the SSR "unknown" state just before hydration
      // restores an earlier explicit choice and removes its button. Only accept
      // that race when the requested state has actually been restored.
      if (await region.getAttribute("data-measurement-choice") !== expected) throw error;
    }
  }
  await page.waitForFunction(
    value => document.querySelector("[data-measurement-choice]")?.getAttribute("data-measurement-choice") === value,
    expected,
    { timeout: 10_000 },
  );
}
