# Edge Bot Defense Playbook

This app already blocks suspicious probes in middleware, but production-grade protection should start at the edge (CDN/WAF) so abusive traffic never reaches app workers.

## 1) Put the app behind an edge WAF/CDN

Recommended providers:

- Cloudflare (Bot Management + WAF + Rate Limiting)
- Fastly + Next-Gen WAF
- AWS CloudFront + AWS WAF

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
