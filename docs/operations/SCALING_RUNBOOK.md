
# Scaling Runbook: 10k Concurrent Users

## Overview

This runbook provides step-by-step instructions for scaling BatchTrack to handle 5,000–10,000 concurrent users. The stack is:

- **Framework**: Flask + SQLAlchemy + Flask-Limiter + Flask-Session
- **Runtime**: Gunicorn (`gevent` workers) running `wsgi:app`
- **Data Stores**: PostgreSQL (primary), Redis (rate limits, caching, sessions)
- **Workers**: Domain-event dispatcher + background scripts
- **Traffic Simulation**: Locust scenarios that mirror production ratios

All guidance below reflects what is currently shipping in the repository—disregard older refactor docs that may contradict these instructions.

## Prerequisites

### Infrastructure Requirements

- **Redis Instance**: High-availability Redis for rate limiting and caching
- **PostgreSQL**: Production database with connection pooling (PgBouncer recommended)
- **Application Servers**: Multiple instances behind a load balancer
- **Monitoring**: Application performance monitoring (APM) and logging

### Minimum Server Specifications (per app instance)

- **CPU**: 4+ cores
- **RAM**: 8GB+ 
- **Network**: High bandwidth, low latency connection
- **Storage**: SSD for logs and temporary files

## Deployment Steps

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

New dependencies added for scaling:
- `redis==5.1.1` - Redis client
- `gevent==24.2.1` - Async worker support  
- `Flask-Caching==2.3.0` - Caching framework

### 2. Environment Configuration

Copy and populate the production environment template:

```bash
cp docs/operations/env.production.example .env.production
```

**Critical settings to configure (minimum for the 5k Locust run):**

```bash
# Core Flask
FLASK_ENV=production
ENV=production
SECRET_KEY=32+char-random-value

# Database connection pool (prevents QueuePool exhaustion)
SQLALCHEMY_POOL_SIZE=80
SQLALCHEMY_MAX_OVERFLOW=40
SQLALCHEMY_POOL_TIMEOUT=45
SQLALCHEMY_POOL_RECYCLE=1800
SQLALCHEMY_POOL_USE_LIFO=true
SQLALCHEMY_POOL_RESET_ON_RETURN=commit

# PostgreSQL (Render/Neon/etc.)
DATABASE_INTERNAL_URL=postgresql://internal-user:...        # Preferred when present
DATABASE_URL=postgresql://external-user:...                 # Fallback for CLI tools

# Redis for rate limiting, caching, and sessions (REQUIRED)
REDIS_URL=redis://your-redis-host:6379/0
RATELIMIT_STORAGE_URI=${REDIS_URL}
RATELIMIT_STORAGE_URL=${REDIS_URL}
RATELIMIT_ENABLED=true
RATELIMIT_DEFAULT="5000 per hour;1000 per minute"            # Matches app/extensions defaults
SESSION_TYPE=redis
CACHE_TYPE=RedisCache
CACHE_REDIS_URL=${REDIS_URL}
CACHE_DEFAULT_TIMEOUT=120

# Gunicorn worker configuration
GUNICORN_WORKERS=8                    # 2x CPU cores + 1
GUNICORN_WORKER_CLASS=gevent
GUNICORN_WORKER_CONNECTIONS=1000
GUNICORN_TIMEOUT=30
GUNICORN_KEEPALIVE=2
GUNICORN_MAX_REQUESTS=2000

# Billing cache (reduces database load)
BILLING_CACHE_ENABLED=true
BILLING_GATE_CACHE_TTL_SECONDS=60
BILLING_STATUS_CACHE_TTL=120

# Locust credential defaults (overridden if LOCUST_USER_CREDENTIALS is set)
LOCUST_USER_BASE=loadtest_user
LOCUST_USER_PASSWORD=loadtest123
LOCUST_USER_COUNT=5000
LOCUST_CACHE_TTL=120

# Domain events & observability
DOMAIN_EVENT_WEBHOOK_URL=https://your-domain-event-endpoint.example
LOG_LEVEL=INFO
SENTRY_DSN=https://your-sentry-dsn
```

> ℹ️ `app/config.py` automatically normalizes `postgres://` URLs to `postgresql://`, so the higher pool sizes above work with Render’s managed PostgreSQL out of the box.

#### 5k Load-Test Environment Checklist

Use the following table when preparing staging/pre-production for a 5,000-user Locust run:

| Category | Variables | Recommended values | Why it matters |
| --- | --- | --- | --- |
| Core Flask runtime | `FLASK_ENV`, `ENV`, `SECRET_KEY` | `production`, `production`, 32+ char key | Enables production config + disables unsafe dev server options. |
| Database connectivity | `DATABASE_INTERNAL_URL`, `DATABASE_URL` | Internal Render URL, fallback external URL | `_normalize_db_url` prefers internal networking for lower latency. |
| SQLAlchemy pooling | `SQLALCHEMY_POOL_SIZE=80`, `SQLALCHEMY_MAX_OVERFLOW=40`, `SQLALCHEMY_POOL_TIMEOUT=45`, `SQLALCHEMY_POOL_RECYCLE=1800`, `SQLALCHEMY_POOL_USE_LIFO=true`, `SQLALCHEMY_POOL_RESET_ON_RETURN=commit` | Ship these verbatim | Prevents the `QueuePool limit of size 5 overflow 10 reached` errors observed in the latest load test logs. |
| Redis + rate limiting | `REDIS_URL`, `RATELIMIT_STORAGE_URI`, `RATELIMIT_STORAGE_URL`, `RATELIMIT_ENABLED=true`, `RATELIMIT_DEFAULT="5000 per hour;1000 per minute"` | Point at HA Redis | Keeps Flask-Limiter aligned with the in-code defaults in `app/extensions.py`. |
| Sessions & cache | `SESSION_TYPE=redis`, `CACHE_TYPE=RedisCache`, `CACHE_REDIS_URL=${REDIS_URL}`, `CACHE_DEFAULT_TIMEOUT=120` | Use Redis for shared state | Avoids Locust 401s caused by per-worker session drift. |
| Billing cache tuning | `BILLING_CACHE_ENABLED=true`, `BILLING_GATE_CACHE_TTL_SECONDS=60`, `BILLING_STATUS_CACHE_TTL=120` | Enabled | Cuts repeated billing queries during recipe dashboards. |
| Worker / Gunicorn | `GUNICORN_WORKERS=8`, `GUNICORN_WORKER_CLASS=gevent`, `GUNICORN_WORKER_CONNECTIONS=1000`, `GUNICORN_TIMEOUT=30`, `GUNICORN_KEEPALIVE=2`, `GUNICORN_MAX_REQUESTS=2000` | Matches `gunicorn.conf.py` | Provides 8×1k concurrent sockets (8k connections) before queueing. |
| Locust credentials | `LOCUST_USER_BASE`, `LOCUST_USER_PASSWORD`, `LOCUST_USER_COUNT`, optional `LOCUST_USER_CREDENTIALS` JSON | `loadtest_user`, `loadtest123`, `5000` | Ensures credential pool has a unique login per virtual user. |
| Locust cache TTL | `LOCUST_CACHE_TTL=120` | 120 seconds | Balances upstream churn with per-user cache hits. |
| Observability | `LOG_LEVEL=INFO`, `SENTRY_DSN`, `ANON_REQUEST_LOG_LEVEL=DEBUG` | As needed | Surface 401/500 spikes quickly during the run. |
| Domain events | `DOMAIN_EVENT_WEBHOOK_URL` | Real webhook or leave blank | When blank, dispatcher logs events but skips HTTP POSTs. |

### 3. Database Optimization

**Connection Pooling Setup:**

The application is configured for high-concurrency database access:

```python
# Configured in app/config.py
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 80,           # Base connections
    'max_overflow': 40,        # Additional connections
    'pool_pre_ping': True,     # Connection health checks
    'pool_recycle': 1800,      # Recycle connections every 30min
    'pool_timeout': 30,        # Connection timeout
    'pool_use_lifo': True,     # LIFO connection reuse
}
```

**Recommended: PgBouncer Setup**

Deploy PgBouncer for additional connection pooling:

```ini
# pgbouncer.ini
[databases]
batchtrack = host=postgres-host port=5432 dbname=batchtrack_prod

[pgbouncer]
pool_mode = transaction
max_client_conn = 200
default_pool_size = 40
```

### 4. Application Server Configuration

**Using the provided Gunicorn configuration:**

```bash
gunicorn -c gunicorn.conf.py wsgi:app
```

**Key Gunicorn settings (auto-configured):**

- **Worker Class**: `gevent` for async I/O
- **Workers**: `2 × CPU cores + 1` 
- **Connections**: `1000 per worker`
- **Timeouts**: `30s request timeout`
- **Memory Management**: `2000 requests per worker restart`
- The `wsgi.py` entrypoint automatically applies `gevent.monkey.patch_all()` when the dependency is installed, but skips patching `thread`/`threading` on Python 3.13+ to avoid upstream gevent bugs (override with `GEVENT_PATCH_THREADS=1` if needed).

#### Domain Event Dispatcher Worker

- Run the outbox dispatcher as a dedicated worker process to flush `domain_event` records to downstream systems.
- Command: `flask dispatch-domain-events` (add `--once` for ad-hoc batches, or configure as a long-running service).
- Provide `DOMAIN_EVENT_WEBHOOK_URL` for webhook delivery; if unset, events are marked processed after logging (no external call).
- Monitor dispatcher logs for retries; events exceeding the retry threshold are tagged with `_dispatch_errors` in the row payload.

#### Shared Session Store

- Flask sessions are now server-side via `Flask-Session`; production **must** point `SESSION_TYPE=redis` and reuse `REDIS_URL` so workers and instances share state.
- Provision Redis (Render Redis, Upstash, AWS ElastiCache, etc.) and copy the URL into both `REDIS_URL` and `RATELIMIT_STORAGE_URI`. If Redis is missing when `FLASK_ENV=production`, the app now raises an error and aborts startup.

### 5. Redis Configuration

**Required for production scaling:**

Redis handles:
- Rate limiting storage
- Billing data caching  
- Session storage (if configured)
- Application logs warn if `RATELIMIT_STORAGE_URI` falls back to `memory://` in production—treat that as a misconfiguration.

**Minimum Redis Configuration:**

```
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
```

### 6. Load Balancer Setup

**Replit Deployments** handle load balancing automatically, but ensure:

- **Health checks**: `GET /health` endpoint
- **Session affinity**: Not required (stateless application)
- **Timeout settings**: Match Gunicorn timeouts

## Performance Validation

### Load Testing

Run the bundled Locust scenarios before every major scale event.

```bash
# Install/upgrade Locust and browser parser dependency
pip install -U "locust>=2.36.0" beautifulsoup4
```

#### Prepare 5k test credentials

Each simulated user needs a unique account to avoid session collisions. Create them (only once per environment) and keep the username/password pattern handy for future runs.

```bash
python loadtests/test_user_generator.py create \
  --count=5000 \
  --username=loadtest_user \
  --password=loadtest123

# Optionally export for non-default naming
export LOCUST_USER_BASE=loadtest_user
export LOCUST_USER_PASSWORD=loadtest123
export LOCUST_USER_COUNT=5000
```

> ℹ️ `loadtests/locustfile.py` falls back to sequential usernames (`loadtest_user1` … `loadtest_user5000`) whenever the `LOCUST_USER_CREDENTIALS` env var is not supplied, so exporting the three variables above is enough for most cases.

#### Scenario mix

| Class              | Weight | Share | Focus areas |
| ------------------ | ------ | ----- | ----------- |
| `RecipeOpsUser`    | 4      | 40%   | Recipe planning, batch creation, library browsing |
| `InventoryOpsUser` | 3      | 30%   | Ingredient lookup, adjustments, expirations |
| `ProductOpsUser`   | 2      | 20%   | SKU audits, product adjustments |
| `AnonymousUser`    | 1      | 10%   | Public pages, signup, catalog cache warming |

Weights map directly to Locust’s user ratios, so any total user count keeps the same production-like blend.

#### Launch the 5k-user run (headless)

```bash
HOST_URL="https://your-app.example.com"  # or http://127.0.0.1:5000 for local tests

locust -f loadtests/locustfile.py \
  --headless \
  --host="${HOST_URL}" \
  -u 5000 \            # total concurrent users
  -r 100 \             # spawn rate (users/second)
  --run-time 30m \
  --logfile logs/locust-5k.log \
  --csv logs/locust-5k
```

Adjust `-r` (spawn rate) based on infrastructure headroom; `100` spawns all users in ~50 seconds and has been stable in staging. Monitor errors such as `auth.login` (500s) or `bootstrap.inventory.api` (401s) closely—persistent failures here usually indicate missing fixtures or throttled services and must be resolved before another high-concurrency attempt.

#### Optional: Web UI smoke test

```bash
locust -f loadtests/locustfile.py \
  --host=http://127.0.0.1:5000 \
  --web-host=0.0.0.0 \
  --users 200 \
  --spawn-rate 10
```

Use the UI to experiment with lower loads, then switch back to the headless command for reproducible 5k-user validation.

### Monitoring Key Metrics

**Application Metrics:**

```python
# Monitor these in logs/APM
- g.billing_gate_cache_state: 'hit'/'miss'/'error'
- Response times by endpoint
- Database connection pool usage
- Redis hit/miss ratios
- Domain event backlog (count of `domain_event` rows where `is_processed=false`)
```

**System Metrics:**

- **CPU Usage**: Should stay below 80% average
- **Memory Usage**: Monitor for memory leaks
- **Database Connections**: Should not hit pool limits
- **Redis Memory**: Monitor cache memory usage

## Troubleshooting

### Common Issues

**1. Database Connection Pool Exhausted**

```
SQLALCHEMY_POOL_SIZE=120
SQLALCHEMY_MAX_OVERFLOW=60
```

**2. Redis Connection Failures**

Check Redis availability and connection string:
```bash
redis-cli -u $REDIS_URL ping
```

**3. High Response Times**

- Check billing cache hit rate
- Verify Gunicorn worker count matches CPU cores
- Monitor database query performance

**4. Memory Usage Growing**

- Gunicorn workers restart after `max_requests`
- Check for memory leaks in application code
- Monitor Redis memory usage

### Performance Tuning

**Database Query Optimization:**

```python
# Enable query logging in development
SQLALCHEMY_ECHO = True

# Monitor slow queries
SQLALCHEMY_ENGINE_OPTIONS['pool_pre_ping'] = True
```

**Cache Tuning:**

```python
# Adjust cache TTL based on usage patterns
BILLING_GATE_CACHE_TTL_SECONDS = 120  # Increase for less frequent updates
```

**Worker Tuning:**

```bash
# Increase workers for CPU-bound workloads
GUNICORN_WORKERS = 16

# Increase connections for I/O-bound workloads  
GUNICORN_WORKER_CONNECTIONS = 2000
```

## Scaling Beyond 10k Users

### Horizontal Scaling

1. **Multi-Instance Deployment**: Deploy multiple app instances
2. **Database Read Replicas**: Separate read/write operations
3. **CDN Integration**: Cache static assets and API responses
4. **Microservices**: Extract high-traffic components

### Advanced Optimizations

1. **Application-Level Caching**: Cache expensive computations
2. **Database Sharding**: Partition data by organization
3. **Queue Workers**: Offload background tasks
4. **Edge Computing**: Deploy closer to users

## Rollback Plan

If issues occur during scaling deployment:

1. **Immediate**: Reduce Gunicorn workers to previous count
2. **Database**: Revert pool size configurations  
3. **Cache**: Disable billing cache if causing issues
4. **Traffic**: Route traffic to stable instance

## Maintenance

### Regular Tasks

- **Weekly**: Review performance metrics and error rates
- **Monthly**: Update dependencies and security patches
- **Quarterly**: Load test and capacity planning review

### Capacity Planning

Monitor these metrics for future scaling decisions:

- **Average response time**: Target < 200ms
- **95th percentile response time**: Target < 1000ms  
- **Database connection usage**: Target < 80% of pool
- **Redis memory usage**: Plan expansion at 80% capacity

---

**Next Steps:**
1. Deploy with this configuration to staging
2. Run comprehensive load tests
3. Monitor metrics for 48 hours
4. Scale to production with confidence
