# Edge Bot Defense Playbook

## Synopsis
Guidance for deploying edge-layer (CDN/WAF) bot protection in front of the Flask app. Covers WAF rules, rate limiting, bot management, and origin hardening.

## Glossary
- **Edge**: CDN/WAF layer that sits between users and the Flask origin.
- **Bot trap**: In-app honeypot endpoint that flags automated scanners (see middleware).

This app already blocks suspicious probes in middleware, but production-grade protection should start at the edge (CDN/WAF) so abusive traffic never reaches app workers.

## 1) Put the app behind an edge WAF/CDN

Recommended providers:

- Cloudflare (Bot Management + WAF + Rate Limiting)
- Fastly + Next-Gen WAF
- AWS CloudFront + AWS WAF

### Step 1 execution (Cloudflare + Render)

Use this sequence for a low-risk first cutover:

1. Add `batchtrack.com` to Cloudflare and import existing DNS records.
2. Proxy the public web records through Cloudflare (orange-cloud) for:
   - apex (`batchtrack.com`)
   - `www.batchtrack.com`
3. Keep non-web records (mail, verification, etc.) DNS-only unless they must traverse the edge.
4. Set SSL/TLS mode to `Full (strict)` and enable HTTPS redirects.
5. Configure a shared origin-auth header at the edge (Transform Rule or Worker), for example:
   - Header: `X-Edge-Origin-Auth`
   - Value: long random secret
6. Configure app env vars:
   - `EDGE_ORIGIN_AUTH_HEADER=X-Edge-Origin-Auth`
   - `EDGE_ORIGIN_AUTH_SECRET=<same-random-secret>`
   - `EDGE_ORIGIN_AUTH_EXEMPT_PATHS=/health`
   - Keep `ENFORCE_EDGE_ORIGIN_AUTH=false` during shadow validation.
7. Validate edge header arrives at origin, then set `ENFORCE_EDGE_ORIGIN_AUTH=true`.
8. If unexpected blocking occurs, rollback by setting `ENFORCE_EDGE_ORIGIN_AUTH=false`.

This repository now supports optional origin-auth enforcement in middleware so direct-to-origin requests can be rejected once the edge is injecting the shared header.

## 2) Enable managed WAF rules

At minimum, enable:

- OWASP Core Ruleset
- Known CMS exploit signatures (WordPress/Joomla/Drupal probes)
- RCE/LFI/path traversal signatures
- Scanner/bot signatures

## 3) Add custom edge block rules for high-noise probes

Block/challenge requests matching:

- `*.php` on non-PHP stack
- `/.git/*`, `/.env*`, `/wp-*`, `/xmlrpc.php`, `/phpmyadmin*`, `/cgi-bin/*`
- `/_profiler/*`, `/vendor/phpunit/*`

Only apply to public hostnames where those paths are never legitimate.

## 4) Rate-limit abusive patterns

Examples:

- Unknown paths: e.g., block/challenge if > 20 requests/minute per IP.
- Auth + checkout starts: e.g., challenge when > 10 attempts/minute per IP.
- API endpoints with anonymous access: enforce strict per-IP limits.

## 5) Bot management policy

- Allow verified search bots (Googlebot/Bingbot) by verified ASN/reverse-DNS policy.
- Challenge or block unverified “crawler-like” user agents.
- Challenge old/empty user agents and known headless automation fingerprints.

## 6) Cache and serve static assets at edge

- Cache immutable static bundles aggressively.
- Prefer 304/edge hits over origin requests.
- Protect origin from cache-bypass floods.

## 7) Origin hardening

- Only accept origin traffic from CDN/WAF egress ranges.
- Deny direct-to-origin traffic where possible.
- Keep strict TLS and HSTS enabled.

## 8) Monitoring and response

- Alert on spikes in 403/404 by path family (`*.php`, `/.git`, `/wp-*`).
- Track top offending IPs/ASNs and auto-ban at edge.
- Keep short retention dashboards for:
  - blocked requests
  - challenged requests
  - origin miss ratio
  - checkout/session start volume

## Suggested first-pass Cloudflare policy

1. Enable Managed WAF + Bot Fight Mode.
2. Custom firewall rule: block if URI path matches `(?i)(^/\.git|^/\.env|^/wp-|xmlrpc\.php|phpmyadmin|/cgi-bin/|/_profiler|vendor/phpunit|\.php$)`.
3. Rate-limit `/auth/signup`, `/auth/signup/checkout`, and checkout-related POST endpoints.
4. Challenge suspicious user agents that are not verified bots.

This combination usually removes the majority of scanner traffic before it reaches Flask.
