"""Validate analytics policy for no-analytics templates.

Synopsis:
Ensures templates rendered from routes that set `load_analytics=False` do not
embed inline analytics emit snippets (`BTAnalytics`, `BTAnalyticsEvents`,
`gtag`, or `posthog.init`).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


_NO_ANALYTICS_TEMPLATES: tuple[str, ...] = (
    "pages/auth/login.html",
    "pages/auth/forgot_password.html",
    "pages/auth/reset_password.html",
    "pages/auth/resend_verification.html",
    "legal/privacy_policy.html",
    "legal/terms_of_service.html",
    "legal/cookie_policy.html",
    "tools/index.html",
    "waitlist/index.html",
    "pages/public/affiliates_info.html",
    "pages/public/affiliates_signup.html",
    "help/how_it_works.html",
    "help/system_faq.html",
)

_BLOCKED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("BTAnalytics usage", re.compile(r"\bBTAnalytics\b")),
    ("BTAnalyticsEvents usage", re.compile(r"\bBTAnalyticsEvents\b")),
    ("gtag usage", re.compile(r"\bgtag\s*\(")),
    ("PostHog init usage", re.compile(r"\bposthog\.init\s*\(")),
)


def _iter_violations(template_path: Path) -> list[str]:
    text = template_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    violations: list[str] = []
    for line_num, line in enumerate(lines, start=1):
        for label, pattern in _BLOCKED_PATTERNS:
            if pattern.search(line):
                violations.append(
                    f"{template_path}:L{line_num} contains {label}: {line.strip()}"
                )
    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    templates_root = repo_root / "app" / "templates"

    violations: list[str] = []
    for rel_path in _NO_ANALYTICS_TEMPLATES:
        template_path = templates_root / rel_path
        if not template_path.exists():
            # Missing templates are ignored to keep the guard resilient to renames.
            continue
        violations.extend(_iter_violations(template_path))

    if violations:
        print("Analytics policy validation failed:", file=sys.stderr)
        for entry in violations:
            print(f"- {entry}", file=sys.stderr)
        return 1

    print("Analytics policy validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

