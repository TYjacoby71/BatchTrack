"""Signup checkout orchestration for auth blueprint routes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from flask import url_for

from ..extensions import db
from ..models.subscription_tier import SubscriptionTier
from .billing_service import BillingService
from .lifetime_pricing_service import LifetimePricingService
from .signup_plan_catalog_service import SignupPlanCatalogService
from .signup_service import SignupService

logger = logging.getLogger(__name__)


@dataclass
class SignupRequestContext:
    db_tiers: list[SubscriptionTier]
    available_tiers: dict[str, dict]
    lifetime_offers: list[dict]
    lifetime_by_key: dict[str, dict]
    lifetime_by_tier_id: dict[str, dict]
    has_lifetime_capacity: bool
    signup_source: str
    referral_code: str | None
    promo_code: str | None
    preselected_tier: str | None
    selected_lifetime_tier: str
    billing_mode: str
    standard_billing_cycle: str
    oauth_user_info: dict | None
    prefill_email: str
    prefill_phone: str


@dataclass
class SignupViewState:
    selected_tier: str | None
    selected_mode: str
    selected_lifetime_key: str
    selected_standard_cycle: str
    contact_email: str
    contact_phone: str
    promo: str | None


@dataclass
class SignupSubmission:
    selected_tier: str | None
    oauth_signup: bool
    contact_email: str
    contact_phone: str
    selected_mode: str
    selected_standard_cycle: str
    billing_cycle_explicit: bool
    selected_lifetime_key: str
    effective_promo_code: str | None
    detected_timezone: str | None
    price_lookup_key_override: str | None = None
    stripe_coupon_id: str | None = None
    stripe_promotion_code_id: str | None = None


@dataclass
class SignupFlowResult:
    redirect_url: str | None = None
    flash_message: str | None = None
    flash_category: str = "error"
    view_state: SignupViewState | None = None


class SignupCheckoutService:
    """Build signup state and execute checkout creation."""

    @classmethod
    def build_request_context(
        cls, *, request, oauth_user_info: dict | None
    ) -> SignupRequestContext:
        db_tiers = SignupPlanCatalogService.load_customer_facing_tiers()
        available_tiers = SignupPlanCatalogService.build_available_tiers_payload(
            db_tiers
        )
        lifetime_offers = LifetimePricingService.build_lifetime_offers(db_tiers)
        lifetime_by_key = LifetimePricingService.map_by_key(lifetime_offers)
        lifetime_by_tier_id = LifetimePricingService.map_by_tier_id(lifetime_offers)

        signup_source = request.args.get("source", request.form.get("source", "direct"))
        referral_code = request.args.get("ref", request.form.get("ref"))
        promo_code = request.args.get("promo", request.form.get("promo"))
        preselected_tier = request.args.get("tier")
        selected_lifetime_tier = request.args.get(
            "lifetime_tier", request.form.get("lifetime_tier", "")
        )
        requested_billing_mode = request.args.get(
            "billing_mode", request.form.get("billing_mode", "")
        )
        requested_billing_cycle = request.args.get(
            "billing_cycle", request.form.get("billing_cycle", "")
        )

        prefill_email = request.form.get("contact_email") or (
            (oauth_user_info or {}).get("email") or ""
        )
        prefill_phone = request.form.get("contact_phone") or ""

        has_lifetime_capacity = LifetimePricingService.any_seats_remaining(
            lifetime_offers
        )
        default_billing_mode = "lifetime" if has_lifetime_capacity else "standard"
        billing_mode = (
            requested_billing_mode
            if requested_billing_mode in {"standard", "lifetime"}
            else default_billing_mode
        )
        default_standard_billing_cycle = (
            "monthly" if has_lifetime_capacity else "yearly"
        )
        standard_billing_cycle = (
            requested_billing_cycle
            if requested_billing_cycle in {"monthly", "yearly"}
            else default_standard_billing_cycle
        )

        if not has_lifetime_capacity:
            billing_mode = "standard"
            selected_lifetime_tier = ""

        if selected_lifetime_tier not in lifetime_by_key:
            selected_lifetime_tier = ""

        if selected_lifetime_tier:
            selected_offer = lifetime_by_key[selected_lifetime_tier]
            if selected_offer.get("tier_id"):
                preselected_tier = selected_offer["tier_id"]
            if not promo_code and selected_offer.get("coupon_code"):
                promo_code = selected_offer["coupon_code"]
        elif billing_mode == "lifetime":
            first_open_offer = cls._preferred_open_lifetime_offer(lifetime_offers)
            if first_open_offer:
                selected_lifetime_tier = first_open_offer["key"]
                if not preselected_tier:
                    preselected_tier = first_open_offer["tier_id"]
                if not promo_code and first_open_offer.get("coupon_code"):
                    promo_code = first_open_offer["coupon_code"]

        if not preselected_tier and db_tiers:
            preferred_default_tier = next(
                (
                    tier
                    for tier in db_tiers
                    if (getattr(tier, "name", "") or "").strip().lower() == "enthusiast"
                ),
                None,
            )
            preselected_tier = str((preferred_default_tier or db_tiers[0]).id)

        return SignupRequestContext(
            db_tiers=db_tiers,
            available_tiers=available_tiers,
            lifetime_offers=lifetime_offers,
            lifetime_by_key=lifetime_by_key,
            lifetime_by_tier_id=lifetime_by_tier_id,
            has_lifetime_capacity=has_lifetime_capacity,
            signup_source=signup_source,
            referral_code=referral_code,
            promo_code=promo_code,
            preselected_tier=preselected_tier,
            selected_lifetime_tier=selected_lifetime_tier,
            billing_mode=billing_mode,
            standard_billing_cycle=standard_billing_cycle,
            oauth_user_info=oauth_user_info or None,
            prefill_email=prefill_email,
            prefill_phone=prefill_phone,
        )

    @staticmethod
    def build_initial_view_state(context: SignupRequestContext) -> SignupViewState:
        return SignupViewState(
            selected_tier=context.preselected_tier,
            selected_mode=context.billing_mode,
            selected_lifetime_key=context.selected_lifetime_tier,
            selected_standard_cycle=context.standard_billing_cycle,
            contact_email=context.prefill_email,
            contact_phone=context.prefill_phone,
            promo=context.promo_code,
        )

    @staticmethod
    def build_template_context(
        context: SignupRequestContext,
        view_state: SignupViewState,
        *,
        oauth_available: bool,
        oauth_providers: dict[str, bool] | None,
        canonical_url: str,
    ) -> dict[str, Any]:
        default_tier_id = view_state.selected_tier or (
            str(context.db_tiers[0].id) if context.db_tiers else ""
        )
        page_title = "BatchTrack Signup | Choose Your Plan"
        page_description = (
            "Simple pricing for makers: Hobbyist, Enthusiast, and Fanatic tiers with monthly, yearly, and limited lifetime options."
            if context.has_lifetime_capacity
            else "Simple pricing for makers: Hobbyist, Enthusiast, and Fanatic tiers with monthly and yearly subscriptions in a calm, batch-first flow."
        )
        return {
            "signup_source": context.signup_source,
            "referral_code": context.referral_code,
            "promo_code": view_state.promo,
            "available_tiers": context.available_tiers,
            "lifetime_offers": context.lifetime_offers,
            "has_lifetime_capacity": context.has_lifetime_capacity,
            "billing_mode": view_state.selected_mode,
            "selected_lifetime_tier": view_state.selected_lifetime_key,
            "standard_billing_cycle": view_state.selected_standard_cycle,
            "oauth_user_info": context.oauth_user_info,
            "oauth_available": oauth_available,
            "oauth_providers": oauth_providers or {"google": False, "facebook": False},
            "preselected_tier": view_state.selected_tier,
            "default_tier_id": default_tier_id,
            "contact_email": view_state.contact_email,
            "contact_phone": view_state.contact_phone,
            "page_title": page_title,
            "page_description": page_description,
            "canonical_url": canonical_url,
        }

    @classmethod
    def process_submission(
        cls, *, context: SignupRequestContext, form_data
    ) -> SignupFlowResult:
        submission = cls._build_submission(context=context, form_data=form_data)

        if not submission.selected_tier:
            return cls._error_result(
                "Please select a subscription plan",
                submission=submission,
                selected_tier=context.preselected_tier,
            )

        if submission.selected_tier not in context.available_tiers:
            return cls._error_result(
                "Invalid subscription plan selected",
                submission=submission,
                selected_tier=context.preselected_tier,
            )

        tier_obj = cls._load_selected_tier(submission.selected_tier)

        if submission.selected_mode == "lifetime":
            lifetime_offer = context.lifetime_by_key.get(
                submission.selected_lifetime_key
            ) or context.lifetime_by_tier_id.get(str(submission.selected_tier))
            if not lifetime_offer:
                return cls._error_result(
                    "Please choose a valid lifetime tier option.",
                    submission=submission,
                    selected_tier=submission.selected_tier,
                    selected_lifetime_key="",
                )

            if not lifetime_offer.get("has_remaining"):
                return cls._error_result(
                    "That lifetime tier is sold out. Please pick another option.",
                    submission=submission,
                    selected_tier=lifetime_offer.get("tier_id")
                    or submission.selected_tier,
                    selected_lifetime_key=lifetime_offer.get("key", ""),
                    selected_standard_cycle="yearly",
                )

            submission.selected_lifetime_key = lifetime_offer.get("key", "")
            mapped_tier_id = lifetime_offer.get("tier_id")
            if mapped_tier_id and mapped_tier_id != submission.selected_tier:
                submission.selected_tier = mapped_tier_id
                tier_obj = cls._load_selected_tier(submission.selected_tier)

            submission.effective_promo_code = (
                lifetime_offer.get("coupon_code") or submission.effective_promo_code
            )
            submission.price_lookup_key_override = (
                lifetime_offer.get("lifetime_lookup_key") or None
            )
            if not submission.price_lookup_key_override:
                return cls._error_result(
                    "Lifetime pricing is not configured for this tier yet.",
                    submission=submission,
                    selected_mode="standard",
                    selected_lifetime_key="",
                    selected_standard_cycle="yearly",
                )

            lifetime_pricing = BillingService.get_live_pricing_for_lookup_key(
                submission.price_lookup_key_override
            )
            if (
                not lifetime_pricing
                or lifetime_pricing.get("billing_cycle") != "one-time"
            ):
                return cls._error_result(
                    "Lifetime pricing must be configured as a one-time Stripe price.",
                    submission=submission,
                    selected_mode="standard",
                    selected_lifetime_key="",
                    selected_standard_cycle="yearly",
                )

            submission.stripe_coupon_id = lifetime_offer.get("stripe_coupon_id") or None
            submission.stripe_promotion_code_id = (
                lifetime_offer.get("stripe_promotion_code_id") or None
            )

        if not tier_obj:
            return cls._error_result(
                "Invalid subscription plan",
                submission=submission,
            )

        if (
            submission.selected_mode == "standard"
            and submission.selected_standard_cycle == "yearly"
        ):
            yearly_lookup_key = (
                LifetimePricingService.resolve_standard_yearly_lookup_key(tier_obj)
            )
            if not yearly_lookup_key:
                if not submission.billing_cycle_explicit:
                    submission.selected_standard_cycle = "monthly"
                else:
                    return cls._error_result(
                        "Yearly billing is not configured for this plan yet.",
                        submission=submission,
                        selected_standard_cycle="monthly",
                    )
            else:
                yearly_pricing = BillingService.get_live_pricing_for_lookup_key(
                    yearly_lookup_key
                )
                if (
                    not yearly_pricing
                    or yearly_pricing.get("billing_cycle") != "yearly"
                ):
                    if not submission.billing_cycle_explicit:
                        submission.selected_standard_cycle = "monthly"
                    else:
                        return cls._error_result(
                            "Yearly billing is temporarily unavailable for this plan.",
                            submission=submission,
                            selected_standard_cycle="monthly",
                        )
                else:
                    submission.price_lookup_key_override = yearly_lookup_key

        metadata = cls._build_checkout_metadata(
            context=context, submission=submission, tier_obj=tier_obj
        )

        try:
            pending_signup = SignupService.create_pending_signup_record(
                tier=tier_obj,
                email=submission.contact_email,
                phone=submission.contact_phone or None,
                signup_source=context.signup_source,
                referral_code=context.referral_code,
                promo_code=submission.effective_promo_code,
                detected_timezone=submission.detected_timezone,
                oauth_user_info=context.oauth_user_info,
                extra_metadata={
                    "preselected_tier": submission.selected_tier,
                    "billing_mode": submission.selected_mode,
                    "billing_cycle": submission.selected_standard_cycle,
                    "lifetime_tier": submission.selected_lifetime_key,
                    **metadata,
                },
            )
        except Exception as exc:
            logger.error("Failed to create pending signup: %s", exc)
            return cls._error_result(
                "Unable to start checkout right now. Please try again later.",
                submission=submission,
            )

        metadata["pending_signup_id"] = str(pending_signup.id)
        success_url = (
            url_for("billing.complete_signup_from_stripe", _external=True)
            + "?session_id={CHECKOUT_SESSION_ID}"
        )
        cancel_url = url_for(
            "auth.signup",
            _external=True,
            billing_mode=submission.selected_mode,
            billing_cycle=(
                submission.selected_standard_cycle
                if submission.selected_mode == "standard"
                else None
            ),
            lifetime_tier=(
                submission.selected_lifetime_key
                if submission.selected_mode == "lifetime"
                else None
            ),
            promo=(
                submission.effective_promo_code
                if submission.selected_mode == "lifetime"
                else None
            ),
        )

        checkout_kwargs = {
            "customer_email": submission.contact_email or None,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata,
            "client_reference_id": str(pending_signup.id),
            "phone_required": False,
        }
        if submission.price_lookup_key_override:
            checkout_kwargs["price_lookup_key_override"] = (
                submission.price_lookup_key_override
            )
        if submission.stripe_coupon_id:
            checkout_kwargs["stripe_coupon_id"] = submission.stripe_coupon_id
        if submission.stripe_promotion_code_id:
            checkout_kwargs["stripe_promotion_code_id"] = (
                submission.stripe_promotion_code_id
            )

        stripe_session = BillingService.create_checkout_session_for_tier(
            tier_obj, **checkout_kwargs
        )
        if stripe_session:
            pending_signup.stripe_checkout_session_id = stripe_session.id
            pending_signup.mark_status("checkout_created")
            db.session.commit()
            return SignupFlowResult(redirect_url=stripe_session.url)

        pending_signup.mark_status("failed", error="session_creation_failed")
        db.session.commit()
        return cls._error_result(
            "Payment system temporarily unavailable. Please try again later.",
            submission=submission,
        )

    @staticmethod
    def _preferred_open_lifetime_offer(lifetime_offers: list[dict]) -> dict | None:
        preferred_offer = next(
            (
                offer
                for offer in lifetime_offers
                if str(offer.get("key", "")).lower() == "enthusiast"
                and offer.get("tier_id")
                and offer.get("has_remaining")
            ),
            None,
        )
        if preferred_offer:
            return preferred_offer
        return next(
            (
                offer
                for offer in lifetime_offers
                if offer.get("tier_id") and offer.get("has_remaining")
            ),
            None,
        )

    @classmethod
    def _build_submission(
        cls, *, context: SignupRequestContext, form_data
    ) -> SignupSubmission:
        selected_mode = form_data.get("billing_mode", "standard")
        selected_mode = (
            selected_mode if selected_mode in {"standard", "lifetime"} else "standard"
        )
        raw_billing_cycle = form_data.get("billing_cycle")
        billing_cycle_explicit = bool(raw_billing_cycle and raw_billing_cycle.strip())
        selected_standard_cycle = raw_billing_cycle or context.standard_billing_cycle
        selected_standard_cycle = (
            selected_standard_cycle
            if selected_standard_cycle in {"monthly", "yearly"}
            else context.standard_billing_cycle
        )
        selected_lifetime_key = form_data.get(
            "lifetime_tier", context.selected_lifetime_tier
        )
        selected_lifetime_key = (
            selected_lifetime_key
            if selected_lifetime_key in context.lifetime_by_key
            else ""
        )

        submission = SignupSubmission(
            selected_tier=form_data.get("selected_tier"),
            oauth_signup=form_data.get("oauth_signup") == "true",
            contact_email=(
                form_data.get("contact_email") or context.prefill_email or ""
            ).strip(),
            contact_phone=(form_data.get("contact_phone") or "").strip(),
            selected_mode=selected_mode,
            selected_standard_cycle=selected_standard_cycle,
            billing_cycle_explicit=billing_cycle_explicit,
            selected_lifetime_key=selected_lifetime_key,
            effective_promo_code=context.promo_code,
            detected_timezone=form_data.get("detected_timezone"),
        )

        if not context.has_lifetime_capacity and submission.selected_mode == "lifetime":
            submission.selected_mode = "standard"
            submission.selected_lifetime_key = ""
            submission.selected_standard_cycle = "yearly"

        return submission

    @staticmethod
    def _load_selected_tier(selected_tier: str | None) -> SubscriptionTier | None:
        try:
            tier_id = int(selected_tier or "")
            return db.session.get(SubscriptionTier, tier_id)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _error_result(
        cls,
        message: str,
        *,
        submission: SignupSubmission,
        selected_tier: str | None = None,
        selected_mode: str | None = None,
        selected_lifetime_key: str | None = None,
        selected_standard_cycle: str | None = None,
        promo: str | None = None,
    ) -> SignupFlowResult:
        view_state = SignupViewState(
            selected_tier=(
                selected_tier if selected_tier is not None else submission.selected_tier
            ),
            selected_mode=(
                selected_mode if selected_mode is not None else submission.selected_mode
            ),
            selected_lifetime_key=(
                selected_lifetime_key
                if selected_lifetime_key is not None
                else submission.selected_lifetime_key
            ),
            selected_standard_cycle=(
                selected_standard_cycle
                if selected_standard_cycle is not None
                else submission.selected_standard_cycle
            ),
            contact_email=submission.contact_email,
            contact_phone=submission.contact_phone,
            promo=promo if promo is not None else submission.effective_promo_code,
        )
        return SignupFlowResult(
            flash_message=message,
            flash_category="error",
            view_state=view_state,
        )

    @staticmethod
    def _build_checkout_metadata(
        *,
        context: SignupRequestContext,
        submission: SignupSubmission,
        tier_obj: SubscriptionTier,
    ) -> dict[str, str]:
        metadata = {
            "tier_id": str(tier_obj.id),
            "tier_name": tier_obj.name,
            "signup_source": context.signup_source,
            "oauth_signup": str(submission.oauth_signup),
            "billing_mode": submission.selected_mode,
            "billing_cycle": (
                "lifetime"
                if submission.selected_mode == "lifetime"
                else submission.selected_standard_cycle
            ),
        }

        if submission.detected_timezone:
            metadata["detected_timezone"] = submission.detected_timezone
            logger.info("Auto-detected timezone: %s", submission.detected_timezone)

        if context.oauth_user_info:
            metadata["oauth_email"] = context.oauth_user_info.get("email", "")
            metadata["oauth_provider"] = context.oauth_user_info.get(
                "oauth_provider", ""
            )
            metadata["oauth_provider_id"] = context.oauth_user_info.get(
                "oauth_provider_id", ""
            )
            metadata["first_name"] = context.oauth_user_info.get("first_name", "")
            metadata["last_name"] = context.oauth_user_info.get("last_name", "")
            metadata["username"] = context.oauth_user_info.get("email", "").split("@")[
                0
            ]
            metadata["email_verified"] = "true"

        if submission.selected_mode == "lifetime":
            metadata["lifetime_tier_key"] = submission.selected_lifetime_key
            if submission.effective_promo_code:
                metadata["lifetime_coupon_code"] = submission.effective_promo_code
            if submission.price_lookup_key_override:
                metadata["lifetime_lookup_key"] = submission.price_lookup_key_override

        if context.referral_code:
            metadata["referral_code"] = context.referral_code
        if submission.effective_promo_code:
            metadata["promo_code"] = submission.effective_promo_code

        return metadata
