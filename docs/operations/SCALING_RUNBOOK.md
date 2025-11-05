# BatchTrack 10k-Concurrency Runbook

This guide captures the infrastructure, operational, and validation steps needed to sustain at least **10,000 simultaneous web sessions**.

## 1. Shared Infrastructure

- **Redis**: Provision a highly-available Redis (AWS Elasticache / Azure Cache) and point `REDIS_URL` + `RATELIMIT_STORAGE_URI` to it. Enable AOF or snapshotting to recover limiter state after failover.
- **Postgres**: Upgrade to a production-class tier with sufficient CPU/IOPS. Enable automatic backups, PITR, and attach at least one read replica for heavy analytics.
- **Connection Pooler**: Deploy PgBouncer (transaction pooling) in front of Postgres; set `SQLALCHEMY_POOL_SIZE`, `SQLALCHEMY_MAX_OVERFLOW`, and PgBouncer pool sizes so total concurrent connections < DB limits.
- **Autoscaling**: Configure app pods/instances with CPU and request-based scaling thresholds (baseline: keep CPU < 65% and queue depth < 10 for >60 seconds).

## 2. Application Runtime

- **Gunicorn/uvicorn**: Use `gunicorn.conf.py` defaults (`gevent` workers, 1000 worker connections). Adjust `GUNICORN_WORKERS` based on available CPU (target 2–4 workers per core for IO-bound traffic).
- **Health checks**: Ensure `/healthz` responds fast and remains isolated from expensive logic. Tie readiness to DB + Redis connectivity.
- **Graceful deploys**: Confirm rolling updates keep at least N healthy pods online and that Gunicorn `graceful_timeout` is honoured.

## 3. Data Path Optimisation

- **Billing gate cache**: Enabled via `_BILLING_CACHE_ENABLED`, default ON. Tune `BILLING_GATE_CACHE_TTL_SECONDS` after measuring load; 30–60 seconds is a good starting point.
- **Query review**: Inspect slow query log and add indexes for any call exceeding 50 ms under load. Prefer CQRS-style read models for dashboards.
- **JSON persistence**: All marketing/settings writes now use atomic file helpers; plan migration to Redis/Postgres for auditability and horizontal scale.

## 4. Observability & Alerting

- **Metrics**: Ship request latency, error rate, DB pool utilisation, Redis memory usage, Gunicorn worker count to your observability stack (Datadog, Grafana, etc.).
- **Logging**: Forward structure logs (JSON) to centralized storage. Include `g.billing_gate_cache_state` to monitor cache efficacy.
- **Alerts**: Create SLO-based alerts for (a) p95 latency > 1s, (b) error rate > 1%, (c) DB connections > 85% saturated, (d) rate limiter backend unreachable.

## 5. Load & Chaos Testing

- **Baseline**: Use `loadtests/locustfile.py` to emulate a mix of public and authenticated traffic. Scale virtual users until p95 > 1s or error rate > 1% and note the break point.
- **Auth flows**: Extend Locust scripts with real login + critical actions (inventory adjustments, recipe management). Use per-env credential vaults.
- **Chaos drills**: Simulate Redis failover, Postgres replica loss, and pod eviction; confirm the app downshifts gracefully (or fails quickly with clear alerts).

## 6. CDN & Front-End

- Serve static assets from S3 + CDN; enable HTTP/2 and gzip/brotli.
- Minify/treeshake JS bundles. Target < 300 KB compressed for initial load. Monitor with WebPageTest.

## 7. Security & Compliance

- Place a WAF in front of the app and enable bot mitigation rules.
- Rotate secrets regularly; store them in a managed secret vault.
- Conduct annual penetration testing and threat modelling as part of SOC2/GDPR readiness.

## 8. Team Readiness

- Document on-call rotations, escalation paths, and communication channels.
- Run quarterly incident response exercises using production-like load and failure scenarios.
- Keep this runbook version-controlled; update after every major scaling change.

---

**Success criteria** for 10k concurrent sessions:

1. Load tests sustain 10k virtual users for 15 minutes with p95 < 1s and <1% errors.
2. No database connection saturation (PgBouncer + DB metrics within safe thresholds).
3. Redis rate-limit storage remains <60% memory usage and latency p95 < 5 ms.
4. Monitoring alerts fire when thresholds are exceeded and include actionable runbook links.

Track these KPIs in your observability dashboards and review before every major product launch.

