"""Affiliate payout status normalization helpers.

Synopsis:
Defines canonical payout statuses and backwards-compatible normalization for
legacy stored values.
"""

from __future__ import annotations

from typing import Final

PAYOUT_STATUS_PENDING: Final[str] = "pending"
PAYOUT_STATUS_SENT: Final[str] = "sent"
PAYOUT_STATUS_COMPLETE: Final[str] = "complete"
PAYOUT_STATUS_UNSUCCESSFUL: Final[str] = "unsuccessful"

LEGACY_TO_CANONICAL: Final[dict[str, str]] = {
    "accrued": PAYOUT_STATUS_PENDING,
    "paid": PAYOUT_STATUS_COMPLETE,
    "failed": PAYOUT_STATUS_UNSUCCESSFUL,
    "unsuccessfull": PAYOUT_STATUS_UNSUCCESSFUL,
    "unsucessfull": PAYOUT_STATUS_UNSUCCESSFUL,
}

CANONICAL_TO_QUERY_VALUES: Final[dict[str, tuple[str, ...]]] = {
    PAYOUT_STATUS_PENDING: (PAYOUT_STATUS_PENDING, "accrued"),
    PAYOUT_STATUS_SENT: (PAYOUT_STATUS_SENT,),
    PAYOUT_STATUS_COMPLETE: (PAYOUT_STATUS_COMPLETE, "paid"),
    PAYOUT_STATUS_UNSUCCESSFUL: (PAYOUT_STATUS_UNSUCCESSFUL, "failed"),
}

VALID_PAYOUT_STATUSES: Final[frozenset[str]] = frozenset(
    {
        PAYOUT_STATUS_PENDING,
        PAYOUT_STATUS_SENT,
        PAYOUT_STATUS_COMPLETE,
        PAYOUT_STATUS_UNSUCCESSFUL,
    }
)

PAYOUT_STATUS_LABELS: Final[dict[str, str]] = {
    PAYOUT_STATUS_PENDING: "Pending",
    PAYOUT_STATUS_SENT: "Sent",
    PAYOUT_STATUS_COMPLETE: "Complete",
    PAYOUT_STATUS_UNSUCCESSFUL: "Unsuccessful",
}


def normalize_payout_status(raw_status: str | None) -> str | None:
    """Return canonical payout status for storage/filtering."""
    cleaned = (raw_status or "").strip().lower()
    if not cleaned:
        return None
    if cleaned in VALID_PAYOUT_STATUSES:
        return cleaned
    return LEGACY_TO_CANONICAL.get(cleaned)


def payout_status_label(raw_status: str | None) -> str:
    """Return human label for a payout status value."""
    canonical = normalize_payout_status(raw_status) or PAYOUT_STATUS_PENDING
    return PAYOUT_STATUS_LABELS.get(canonical, "Pending")


def payout_status_query_values(raw_status: str | None) -> tuple[str, ...]:
    """Return storage values that should match the provided canonical status."""
    canonical = normalize_payout_status(raw_status)
    if not canonical:
        return ()
    return CANONICAL_TO_QUERY_VALUES.get(canonical, ())


def is_payout_complete(raw_status: str | None) -> bool:
    """Return True when payout status is complete/paid."""
    return normalize_payout_status(raw_status) == PAYOUT_STATUS_COMPLETE
