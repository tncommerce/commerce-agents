// Native-browser QA helper. qa=1 and URL parameters never grant optional
// measurement; positive fixtures make an explicit, ordinary UI choice.
export async function chooseMeasurement(page, choice = "granted") {
  const expected = choice === "granted" ? "granted" : "denied";
  const region = page.locator("[data-measurement-choice]").first();
  await region.waitFor({ state: "attached", timeout: 10_000 });
  // The server renders "unknown" before reading the saved browser choice.
  // Wait for either the hydrated choice or the initial choice controls so a
  // subsequent page does not race a persisted denial and click a removed button.
  await page.waitForFunction(() => {
    const region = document.querySelector("[data-measurement-choice]");
    return region?.getAttribute("data-measurement-choice") !== "unknown" ||
      [...document.querySelectorAll("button")].some(button =>
        button.textContent?.trim() === "Nur notwendige Funktionen");
  });
  const current = await region.getAttribute("data-measurement-choice");
  if (current === expected) return;
  if (current === "granted" && expected === "denied") {
    await page.getByRole("button", { name: "Analyse widerrufen", exact: true }).click();
  } else {
    if (current !== "unknown") {
      await page.getByRole("button", { name: "Datenschutz-Einstellungen", exact: true }).click();
    }
    const name = expected === "granted" ? "Analyse erlauben" : "Nur notwendige Funktionen";
    await page.getByRole("button", { name, exact: true }).click();
  }
  await page.waitForFunction(
    value => document.querySelector("[data-measurement-choice]")?.getAttribute("data-measurement-choice") === value,
    expected,
    { timeout: 10_000 },
  );
}
