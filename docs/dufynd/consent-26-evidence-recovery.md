# CONSENT-26: bounded evidence recovery

15 October 2026. Parent 783a135488368c071110fed44a209c837abfc49b.
Existing draft PR #794; no application, database, schedule or deployment change.

## Verified incoming state

CI 38735370388 is not green. The Python 3.12 run had 3476 passes and
five failures, all in the offline evidence acceptance suite, no setup errors.
The latest original browser artifact 11973532445 (34,998,723 bytes) was verified
against SHA256 a4ad36a8b9c912b7aa22b0efb0e34c85378942be10bc7a5809501cd82db1e087
and ZIP CRC. Its report has 130 passed / 12 failed checks, compared with
37 failed checks on the preceding bf45ff development run. Seven dedicated
native consent scenarios pass on 783a135: 320/390/768/1440, cross-tab,
in-flight withdrawal and blocked preference storage. No real merchant click.
These are parent results, not approval of the new commit.

## Actual change

The allowlisted source set and its hard 24,576-byte packet budget are unchanged.
Core funnel evidence now precedes secondary diagnostics. Over-wide client code
windows are narrowed around explicit acquisition, identity, consent and withdrawal
anchors. API windows include the real multiline redirect and event-recording code.
The checker accepts the actual separate RedirectResponse( / url=target, tokens,
not a formatting-specific one-line spelling, and now additionally requires client
and server consent-gate evidence.

When a required source or quote is absent, the fixture emits no invented claim.
The independent checker can return needs_more_evidence instead of maker_fixture
crashing with StopIteration. Incomplete evidence still blocks task completion,
next-task selection, publishing and automatic paid retry. Nothing is dispatched.
The content projection and content source priority policy are not changed.

## Executed local verification

The baseline worker and acceptance files were byte-matched to Git blobs
e4bb82636595630b84a99f9e4b35078a940a211c and
2bccd5765cf14d551795d792d01d0babdeec8a2a before editing.
The unchanged independent checker was matched to 5bbb8fbd32986bc455ca6659ee1b9ea07383078f.

Six focused offline algorithm cases passed using synthetic temporary repository
inputs. The same two missing-source cases fail on the exact original acceptance
code with StopIteration. No provider or external network requests occurred.
The new full-checkout coverage/hash/line-range test is intentionally reserved for
CI, because this local session does not contain the full repository snapshot.
No claim that the five repository-wide failures are closed until CI confirms it.

## Remaining work

The twelve remaining browser failures are not changed by this evidence patch:
merchant-offer retry is intercepted by the undecided preference panel; legacy
positive analytics/offer/merchant/navigation/comparison cases need explicit UI
consent, query-aware mocks and independent measurement-identity expectations.
Keep separate default-off/deny/revoke paths and real shopping assertions.
Do not bypass consent globally or weaken unavailable-offer and destination gates.

Server-side revocation of copied granted URLs, retention/deletion, provider terms,
photo rights and final integrated quality remain separate unfinished requirements.
No new Nightshift, permission, purchase, contact, social post or production change.
