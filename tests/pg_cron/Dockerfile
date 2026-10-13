# Disposable CI only. Same extension release observed in the hosted project.
FROM postgres:17
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates curl postgresql-server-dev-17 \
    && curl --fail --location --retry 2 https://github.com/citusdata/pg_cron/archive/refs/tags/v1.6.4.tar.gz -o /tmp/pg_cron.tar.gz \
    && mkdir /tmp/pg_cron \
    && tar -xzf /tmp/pg_cron.tar.gz --strip-components=1 -C /tmp/pg_cron \
    && make -C /tmp/pg_cron \
    && make -C /tmp/pg_cron install \
    && rm -rf /tmp/pg_cron /tmp/pg_cron.tar.gz /var/lib/apt/lists/*
