import { chromium } from "playwright";
import { verifyConversionSearch } from "./conversion-search-qa.mjs";

const browser = await chromium.launch({headless: true});
try {
  const cases = await verifyConversionSearch(browser, "http://127.0.0.1:3000", null);
  console.log("DUFYND_CONVERSION_QA_PASS", JSON.stringify({cases: cases.length}));
} catch (error) {
  console.error("DUFYND_CONVERSION_QA_FAIL", error.stack || String(error));
  process.exitCode = 1;
} finally {
  await browser.close();
}
