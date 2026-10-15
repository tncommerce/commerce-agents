# CONSENT-26: mounted-product consent lifecycle

15 October 2026. Parent 5dadb8f41042345c36c18e4eb793b5d0787277cd.
Existing PR #794 / dufynd-consent-26-20261015. Development only.

## Source defect addressed

FragranceOffers previously attempted detail/impression tracking at mount and
consumed its tracked refs even when the analytics helper declined measurement.
Its session readiness was also checked only at mount/retry. Granting permission
later therefore did not initialize all mounted product measurement state.
AcquisitionInternalLink updated React href state only when its href prop changed;
native focus/click hooks could repair the href, but an explicit choice did not
update the already-rendered link state.

This is a source-identified lifecycle defect, not proof that production customer
events were lost. The consent branch has not been deployed.

## Implemented in this atomic change

- Subscribe mounted product measurement to the existing consent store. Default or
  denied choice leaves functional merchant links ready and does not consume
  tracking refs. Grant measures the current product, not historical actions.
- Separate functional offer fetching from permission changes. Consent itself
  does not reload offer data or alter prices, variants, ranking or image rights.
- Bound pending session callbacks to the active subscription attempt. Withdrawal
  prevents late callbacks re-blocking or updating the old measurement state.
- Observe current offer visibility only under consent; disconnect/reset on denial.
  Reaffirming an enabled choice does not double count the same product/impression.
- React internal-link href state also subscribes to choice changes. Original native
  navigation handlers and the existing strict destination boundary remain.

## Executable proof added — not yet a PASS claim

The exact original measurement-browser-qa.mjs source (blob
b354c00a5f3a066ddeadcd572a79c10104d48c70) is preserved unchanged as
measurement-browser-core-qa.mjs. The original entry point now calls all seven
original scenarios followed by four new native late-grant scenarios, at widths
320, 390, 768 and 1440. The combined report cannot remain PASS if the later block
fails. No original unknown/deny/cross-tab/in-flight/blocked-storage scenario is
removed, no positive permission is preseeded, and no forced click is used.

New scenarios exercise actual UI choice after the product and offers loaded;
assert no telemetry before choice; verify href updates WITHOUT focus/click repair;
require one current detail/impression with an independent UUID; check no duplicate
on reaffirmation; verify withdrawn links and no post-withdrawal measurement; then
require a new identity on regrant without resurrecting the old campaign. Functional
offer fetch counts cannot increase simply because consent changes.

All browser API responses are synthetic or blocked; merchant redirects are never
followed. These new scenarios have NOT been locally executed in this session:
the container/Python runtime returned ClientError. Do not label static review or
uploaded blobs as executed tests. Existing standard PR CI must supply the real
build, TypeScript, browser and independent regression result.

## Remaining work / today's acceptance target

Close the remaining legacy positive browser fixtures using explicit UI choice,
query-aware analytics mocks and independent measurement IDs. Default/denial and
shopping checks must remain independent. Today's target is a fully tested consent
integration and genuine preview evidence, not a guaranteed public launch or
income. An individual native PASS cannot substitute for full CI.

Server-side copied-grant URL revocation, factual privacy disclosure,
purpose-bound retention/deletion, provider agreements and exact Rabanne image
rights remain separately open. No protected merge, deployment, live data change,
paid service, duplicate image-rights email, new Nightshift or social work.
