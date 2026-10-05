# First Money Launch Day Operations V1

The launch runtime counts only the exact configured content and experiment, Instagram/TikTok,
and 1 Million product events (null product is accepted for page_view). Each platform's
scheduled timestamp is its lower measurement bound; future events and prelaunch QA are excluded.
Attribution proves a tagged visit, not organic reach or publication.

The five eligible event types queue one existing certified supervisor_state_audit per
content/experiment and ten-minute ingestion bucket. Ingestion time prevents delayed/client
signals from opening unlimited historical task buckets. No new worker, provider call, publishing,
product activation, external message or credential is enabled. Audit packets persist the runtime.

The Control Room prefers fresh version-2 runtime counts and source/freshness labels. It shows
traffic, product interest, offer interest and merchant clickout as successive signals. Transactions
and commission remain unknown until authoritative affiliate-network evidence is available.
Network transaction ingestion is not connected; nothing derives a sale from a clickout.
Metricool publication remains a read-only snapshot, not continuous confirmation.

Validation: launch SQL fixtures and existing Thin-V1 execution/gate regression on the live
schema inside rolled-back transactions; dashboard projection and affiliate attribution tests;
production read-only smoke 18/18. Real production QA uses qa_launch_preflight_20261005 and
is excluded from launch counts. No redirect is followed to an affiliate network or merchant.

Use tests/sql_dufynd_launch_day.sql in a transaction; its fixtures always roll back.
The two scheduled Metricool posts and Delina product page are unchanged.
