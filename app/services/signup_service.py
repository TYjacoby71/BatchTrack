"""Signup orchestration for pending checkout and account provisioning.

Synopsis:
Creates pending signup records before checkout and provisions org/user records after payment.
Coordinates verification/reset token issuance and welcome/setup notifications.

Glossary:
- Pending signup: Pre-checkout record tracking email, tier, and checkout state.
- Provisioning: Materializing organization + owner user from checkout artifacts.
"""

import logging
import secrets
from typing import Optional, Tuple

from ..models import Organization, PendingSignup, Role, SubscriptionTier, User, db
from ..utils.timezone_utils import TimezoneUtils
from .batchbot_credit_service import BatchBotCreditService
from .email_service import EmailService
from .event_emitter import EventEmitter

# Import moved to avoid circular dependency
# from ..blueprints.developer.subscription_tiers import load_tiers_config

logger = logging.getLogger(__name__)


# --- Signup service ---
# Purpose: Orchestrate pending signup records and post-checkout account provisioning.
# Inputs: Tier/signup metadata, provider checkout artifacts, and organization defaults.
# Outputs: PendingSignup records or provisioned Organization/User tuples.
class SignupService:
    """Service for handling complete signup and organization creation"""

    # ------------------------------------------------------------------ #
    # New Stripe checkout orchestration                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_pending_signup_record(
        *,
        tier: SubscriptionTier,
        email: str,
        phone: Optional[str],
        signup_source: Optional[str],
        referral_code: Optional[str],
        promo_code: Optional[str],
        detected_timezone: Optional[str],
        oauth_user_info: Optional[dict],
        extra_metadata: Optional[dict] = None,
    ) -> PendingSignup:
        """Persist a pending signup row before redirecting the user to Stripe."""
        cleaned_email = (email or "").strip().lower()
        if not cleaned_email:
            cleaned_email = SignupService._generate_placeholder_email()

        pending = PendingSignup(
            email=cleaned_email,
            phone=(phone or "").strip() or None,
            signup_source=signup_source or "direct",
            referral_code=(referral_code or "").strip() or None,
            promo_code=(promo_code or "").strip() or None,
            detected_timezone=detected_timezone or None,
            tier_id=tier.id,
            oauth_provider=(oauth_user_info or {}).get("oauth_provider"),
            oauth_provider_id=(oauth_user_info or {}).get("oauth_provider_id"),
            extra_metadata=extra_metadata or {},
        )

        db.session.add(pending)
        db.session.commit()
        logger.info(
            "Created pending signup %s for %s (tier %s)",
            pending.id,
            cleaned_email,
            tier.id,
        )
        return pending

    @staticmethod
    # --- Complete pending signup from checkout ---
    # Purpose: Create org + owner user after payment and initialize setup tokens/emails.
    def complete_pending_signup_from_checkout(
        pending_signup: PendingSignup,
        checkout_session,
        customer_obj,
    ) -> Tuple[Optional[Organization], Optional[User]]:
        """
        Materialize the organization + owner user after checkout.session.completed.
        Returns the org/user pair (existing or newly created).
        """
        if not pending_signup:
            return None, None

        if (
            pending_signup.status == "account_created"
            and pending_signup.organization_id
            and pending_signup.user_id
        ):
            logger.info("Pending signup %s already fulfilled", pending_signup.id)
            org = db.session.get(Organization, pending_signup.organization_id)
            user = db.session.get(User, pending_signup.user_id)
            return org, user

        subscription_tier = pending_signup.tier or db.session.get(
            SubscriptionTier, pending_signup.tier_id
        )
        if not subscription_tier:
            raise ValueError(
                f"Subscription tier {pending_signup.tier_id} not found for pending signup {pending_signup.id}"
            )

        session_metadata = SignupService._object_to_dict(
            getattr(checkout_session, "metadata", {})
        )
        customer_details = SignupService._object_to_dict(
            getattr(checkout_session, "customer_details", {})
        )
        customer_metadata = SignupService._object_to_dict(
            getattr(customer_obj, "metadata", {})
        )
        pending_extra_metadata = pending_signup.extra_metadata or {}
        custom_fields = getattr(checkout_session, "custom_fields", None)

        pending_signup.stripe_checkout_session_id = (
            pending_signup.stripe_checkout_session_id
            or getattr(checkout_session, "id", None)
        )
        pending_signup.stripe_customer_id = (
            pending_signup.stripe_customer_id or getattr(customer_obj, "id", None)
        )
        pending_signup.mark_status("checkout_completed")

        oauth_email = SignupService._first_non_empty(
            session_metadata.get("oauth_email"),
            pending_extra_metadata.get("oauth_email"),
        )
        email = SignupService._first_non_empty(
            customer_details.get("email"),
            getattr(customer_obj, "email", None),
            oauth_email,
            pending_signup.email,
        )
        # Never keep placeholder pending email when we have an OAuth identity email.
        if (
            email
            and isinstance(email, str)
            and email.endswith("@signup.batchtrack")
            and oauth_email
        ):
            email = oauth_email
        if not email:
            raise ValueError("Stripe checkout session missing customer email")

        phone = SignupService._first_non_empty(
            customer_details.get("phone"),
            getattr(customer_obj, "phone", None),
            pending_signup.phone,
        )
        pending_signup.email = email
        pending_signup.phone = phone

        full_name = SignupService._first_non_empty(
            customer_details.get("name"),
            getattr(customer_obj, "name", None),
        )
        first_name, last_name = SignupService._split_name(full_name)
        metadata_first_name = SignupService._first_non_empty(
            session_metadata.get("first_name"),
            pending_extra_metadata.get("first_name"),
        )
        metadata_last_name = SignupService._first_non_empty(
            session_metadata.get("last_name"),
            pending_extra_metadata.get("last_name"),
        )
        custom_first = SignupService._extract_custom_field(custom_fields, "first_name")
        custom_last = SignupService._extract_custom_field(custom_fields, "last_name")
        if custom_first and not first_name:
            first_name = custom_first
        if custom_last and not last_name:
            last_name = custom_last
        if metadata_first_name and not first_name:
            first_name = metadata_first_name
        if metadata_last_name and not last_name:
            last_name = metadata_last_name

        workspace_field = SignupService._extract_custom_field(
            custom_fields, "workspace_name"
        )
        org_name = (
            workspace_field
            or session_metadata.get("org_name")
            or customer_metadata.get("org_name")
            or pending_extra_metadata.get("org_name")
        )
        if not org_name:
            org_name = f"{first_name or 'New'}'s Workspace"

        username = SignupService._generate_username(email)

        try:
            verification_enabled = EmailService.should_issue_verification_tokens()
            org = Organization(
                name=org_name,
                contact_email=email,
                is_active=True,
                signup_source=pending_signup.signup_source or "stripe",
                promo_code=pending_signup.promo_code,
                referral_code=pending_signup.referral_code,
                subscription_tier_id=subscription_tier.id,
                stripe_customer_id=pending_signup.stripe_customer_id,
                billing_status="active",
                subscription_status="active",
            )
            db.session.add(org)
            db.session.flush()

            owner_user = User(
                username=username,
                email=email,
                first_name=first_name or "",
                last_name=last_name or "",
                phone=phone,
                organization_id=org.id,
                user_type="customer",
                is_organization_owner=True,
                is_active=True,
                email_verified=not verification_enabled,
                email_verification_token=(
                    EmailService.generate_verification_token(email)
                    if verification_enabled
                    else None
                ),
                email_verification_sent_at=(
                    TimezoneUtils.utc_now() if verification_enabled else None
                ),
                oauth_provider=pending_signup.oauth_provider,
                oauth_provider_id=pending_signup.oauth_provider_id,
            )
            owner_user.set_password(secrets.token_urlsafe(16))
            db.session.add(owner_user)
            db.session.flush()
            owner_user.timezone = pending_signup.detected_timezone or "UTC"

            org_owner_role = Role.query.filter_by(
                name="organization_owner", is_system_role=True
            ).first()
            if org_owner_role:
                owner_user.assign_role(org_owner_role)

            pending_signup.organization_id = org.id
            pending_signup.user_id = owner_user.id
            pending_signup.mark_status("account_created")

            # Prepare password setup + welcome email tokens
            reset_token = EmailService.generate_reset_token(owner_user.id)
            owner_user.password_reset_token = reset_token
            owner_user.password_reset_sent_at = TimezoneUtils.utc_now()

            db.session.commit()

            try:
                BatchBotCreditService.grant_signup_bonus(org)
            except Exception as bonus_error:
                logger.warning("Failed to grant BatchBot signup bonus: %s", bonus_error)

            if verification_enabled:
                try:
                    EmailService.send_verification_email(
                        owner_user.email,
                        owner_user.email_verification_token,
                        owner_user.first_name or owner_user.username,
                    )
                except Exception as email_error:
                    logger.warning("Failed to send verification email: %s", email_error)

            try:
                EmailService.send_welcome_email(
                    owner_user.email,
                    owner_user.first_name or owner_user.username,
                    org.name,
                    subscription_tier.name,
                )
            except Exception as email_error:
                logger.warning("Failed to send welcome email: %s", email_error)

            try:
                EmailService.send_password_setup_email(
                    owner_user.email,
                    reset_token,
                    owner_user.first_name or owner_user.username,
                )
            except Exception as email_error:
                logger.warning("Failed to send password setup email: %s", email_error)

            EventEmitter.emit(
                "billing.stripe_checkout_completed",
                organization_id=org.id,
                user_id=owner_user.id,
                properties={
                    "pending_signup_id": pending_signup.id,
                    "tier_id": subscription_tier.id,
                    "checkout_session_id": pending_signup.stripe_checkout_session_id,
                    "stripe_customer_id": pending_signup.stripe_customer_id,
                },
                auto_commit=True,
            )
            promo_code = (pending_signup.promo_code or "").strip() or None
            referral_code = (pending_signup.referral_code or "").strip() or None
            completion_properties = {
                "pending_signup_id": pending_signup.id,
                "tier_id": subscription_tier.id,
                "signup_source": pending_signup.signup_source or "direct",
                "checkout_session_id": pending_signup.stripe_checkout_session_id,
                "stripe_customer_id": pending_signup.stripe_customer_id,
                "billing_provider": "stripe",
                "signup_flow": "checkout",
                "is_oauth_signup": bool(pending_signup.oauth_provider),
                "used_promo_code": bool(promo_code),
                "promo_code": promo_code,
                "used_referral_code": bool(referral_code),
                "referral_code": referral_code,
            }
            try:
                raw_first_landing = (
                    (pending_signup.metadata or {}).get("client_first_landing_at")
                    if isinstance(pending_signup.metadata, dict)
                    else None
                )
                if raw_first_landing not in (None, ""):
                    first_landing_ms = int(str(raw_first_landing).strip())
                    if 946684800000 <= first_landing_ms <= 4102444800000:
                        now_ms = int(TimezoneUtils.utc_now().timestamp() * 1000)
                        completion_properties["seconds_since_first_landing"] = int(
                            max(0, (now_ms - first_landing_ms) / 1000)
                        )
            except (TypeError, ValueError):
                pass
            EventEmitter.emit(
                "signup_completed",
                organization_id=org.id,
                user_id=owner_user.id,
                properties=completion_properties,
                entity_type="organization",
                entity_id=org.id,
                auto_commit=True,
            )
            EventEmitter.emit(
                "signup_checkout_completed",
                organization_id=org.id,
                user_id=owner_user.id,
                properties=completion_properties,
                entity_type="organization",
                entity_id=org.id,
                auto_commit=True,
            )
            EventEmitter.emit(
                "purchase_completed",
                organization_id=org.id,
                user_id=owner_user.id,
                properties=completion_properties,
                entity_type="organization",
                entity_id=org.id,
                auto_commit=True,
            )

            return org, owner_user

        except Exception as exc:
            db.session.rollback()
            logger.error(
                "Failed to complete pending signup %s: %s", pending_signup.id, exc
            )
            fresh = db.session.get(PendingSignup, pending_signup.id)
            if fresh:
                fresh.mark_status("failed", error=str(exc))
                db.session.commit()
            raise

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _object_to_dict(obj):
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        try:
            return obj.to_dict_recursive()
        except AttributeError:
            try:
                return dict(obj)
            except Exception:
                return {}

    @staticmethod
    def _first_non_empty(*values):
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and value.strip() == "":
                continue
            return value
        return None

    @staticmethod
    def _split_name(full_name: Optional[str]) -> Tuple[str, str]:
        if not full_name:
            return "", ""
        parts = full_name.strip().split()
        if not parts:
            return full_name, ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])

    @staticmethod
    def _generate_username(email: str) -> str:
        base = (email or "user").split("@")[0]
        base = "".join(ch for ch in base if ch.isalnum()) or "user"
        candidate = base
        counter = 1
        while User.query.filter_by(username=candidate).first():
            candidate = f"{base}{counter}"
            counter += 1
        return candidate

    @staticmethod
    def _generate_placeholder_email() -> str:
        return f"pending+{secrets.token_hex(6)}@signup.batchtrack"

    @staticmethod
    def _extract_custom_field(custom_fields, key: str):
        try:
            for field in custom_fields or []:
                current_key = (
                    getattr(field, "key", None)
                    if not isinstance(field, dict)
                    else field.get("key")
                )
                if current_key != key:
                    continue
                payload = (
                    getattr(field, "text", None)
                    if not isinstance(field, dict)
                    else field.get("text")
                )
                if isinstance(payload, dict):
                    return payload.get("value")
        except Exception:
            return None
        return None
