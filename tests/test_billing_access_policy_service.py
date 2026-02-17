from types import SimpleNamespace

from app.services.billing_access_policy_service import (
    BillingAccessAction,
    BillingAccessPolicyService,
)
from app.services.billing_service import BillingService


def _org(*, billing_status="active", is_active=True, is_billing_exempt=False):
    return SimpleNamespace(
        is_active=is_active,
        billing_status=billing_status,
        subscription_tier_obj=SimpleNamespace(is_billing_exempt=is_billing_exempt),
    )


def test_hard_lock_when_organization_inactive():
    decision = BillingAccessPolicyService.evaluate_organization(
        _org(is_active=False, billing_status="active")
    )
    assert decision.action == BillingAccessAction.HARD_LOCK
    assert decision.reason == "organization_inactive"


def test_hard_lock_when_subscription_canceled():
    decision = BillingAccessPolicyService.evaluate_organization(
        _org(is_active=True, billing_status="canceled")
    )
    assert decision.action == BillingAccessAction.HARD_LOCK
    assert decision.reason == "organization_inactive"


def test_recoverable_status_requires_upgrade():
    decision = BillingAccessPolicyService.evaluate_organization(
        _org(is_active=True, billing_status="past_due", is_billing_exempt=False)
    )
    assert decision.action == BillingAccessAction.REQUIRE_UPGRADE
    assert decision.reason == "billing_required"


def test_exempt_tier_skips_recoverable_redirect(monkeypatch):
    monkeypatch.setattr(
        BillingService,
        "validate_tier_access",
        lambda _organization: (True, "exempt_tier"),
    )
    decision = BillingAccessPolicyService.evaluate_organization(
        _org(is_active=True, billing_status="past_due", is_billing_exempt=True)
    )
    assert decision.action == BillingAccessAction.ALLOW


def test_validate_tier_access_payment_required_maps_to_upgrade(monkeypatch):
    monkeypatch.setattr(
        BillingService,
        "validate_tier_access",
        lambda _organization: (False, "payment_required"),
    )
    decision = BillingAccessPolicyService.evaluate_organization(
        _org(is_active=True, billing_status="active", is_billing_exempt=False)
    )
    assert decision.action == BillingAccessAction.REQUIRE_UPGRADE
    assert decision.reason == "payment_required"


def test_validate_tier_access_subscription_canceled_maps_to_hard_lock(monkeypatch):
    monkeypatch.setattr(
        BillingService,
        "validate_tier_access",
        lambda _organization: (False, "subscription_canceled"),
    )
    decision = BillingAccessPolicyService.evaluate_organization(
        _org(is_active=True, billing_status="active", is_billing_exempt=False)
    )
    assert decision.action == BillingAccessAction.HARD_LOCK
    assert decision.reason == "subscription_canceled"


def test_unknown_validation_reason_defaults_to_allow(monkeypatch):
    monkeypatch.setattr(
        BillingService,
        "validate_tier_access",
        lambda _organization: (False, "no_tier_assigned"),
    )
    decision = BillingAccessPolicyService.evaluate_organization(
        _org(is_active=True, billing_status="active", is_billing_exempt=False)
    )
    assert decision.action == BillingAccessAction.ALLOW
    assert decision.reason == "no_tier_assigned"


def test_billing_enforcement_exempt_route_matching():
    assert (
        BillingAccessPolicyService.is_enforcement_exempt_route("/billing/upgrade", None)
        is True
    )
    assert (
        BillingAccessPolicyService.is_enforcement_exempt_route(
            "/dashboard", "billing.upgrade"
        )
        is True
    )
    assert (
        BillingAccessPolicyService.is_enforcement_exempt_route(
            "/dashboard", "app_routes.dashboard"
        )
        is False
    )
