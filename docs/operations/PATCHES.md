# Patch Log

This document tracks temporary patches or workarounds that diverge from
upstream behavior. Each entry has a unique identifier referenced in code via
`[PATCH-XXX]` so we can audit and retire them once the upstream issue is
resolved.

| Patch ID   | Location(s)              | Summary                                                                 | Introduced | Removal Criteria                                  |
|------------|--------------------------|-------------------------------------------------------------------------|------------|---------------------------------------------------|
| PATCH-001  | `wsgi.py` (`_gevent_patch_kwargs`) | Disable gevent's thread/threading monkey-patching on Python ≥ 3.13 to avoid `AssertionError`/`KeyError` crashes when wrapping `threading.Timer`. Controlled via `GEVENT_PATCH_THREADS`. | 2025-11-15 | Remove after gevent releases a version fully compatible with Python 3.13 threading internals (or when we downgrade/replace gevent). |

## Process

1. When implementing a workaround, annotate the relevant code block with
   `[PATCH-XXX]` and add an entry here.
2. Cross-link any upstream issue tracker URLs if available.
3. Review this document during maintenance windows to retire patches that are
   no longer needed.
