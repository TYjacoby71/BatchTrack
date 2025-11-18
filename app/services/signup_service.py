
import logging
import secrets
from typing import Optional, Tuple

from flask import session, flash, current_app, redirect, url_for
from flask_login import login_user

from ..models import db, User, Organization, Role, SubscriptionTier, PendingSignup
from ..utils.timezone_utils import TimezoneUtils
from .session_service import SessionService
from .email_service import EmailService
from .event_emitter import EventEmitter
# Import moved to avoid circular dependency
# from ..blueprints.developer.subscription_tiers import load_tiers_config

logger = logging.getLogger(__name__)

class SignupService:
    """Service for handling complete signup and organization creation"""

    @staticmethod
    def complete_signup(tier):
        """Complete organization creation and user signup"""
        logger.info(f"=== SIGNUP COMPLETION START ===")
        logger.info(f"Requested tier: {tier}")

        flash('Creating your account now...', 'info')

        # Get pending signup data from session
        pending_signup = session.get('pending_signup')
        if not pending_signup:
            logger.error("No pending signup found in session")
            flash('No pending signup found. Please start the signup process again.', 'error')
            return redirect(url_for('auth.signup'))

        logger.info(f"=== PENDING SIGNUP DATA ===")
        logger.info(f"Username: {pending_signup.get('username')}")
        logger.info(f"Selected tier in signup: {pending_signup.get('selected_tier')}")
        logger.info(f"Tier being processed: {tier}")
        logger.info(f"Organization name: {pending_signup.get('org_name')}")
        logger.info(f"Email: {pending_signup.get('email')}")
        logger.info(f"==========================")

        # Verify tier consistency
        signup_tier = pending_signup.get('selected_tier')
        if signup_tier and signup_tier != tier:
            logger.warning(f"Tier mismatch! Signup had {signup_tier}, processing {tier}")
            logger.info(f"Using tier from checkout: {tier}")

        # No JSON-based tier config; rely on DB only
        logger.info(f"Final tier check using DB - tier '{tier}' being processed")

        try:
            # Get the subscription tier
            subscription_tier = SubscriptionTier.find_by_identifier(tier)
            if not subscription_tier:
                raise Exception(f"Subscription tier '{tier}' not found")

            # Create organization
            org = Organization(
                name=pending_signup['org_name'],
                contact_email=pending_signup['email'],
                is_active=True,
                signup_source=pending_signup['signup_source'],
                promo_code=pending_signup.get('promo_code'),
                referral_code=pending_signup.get('referral_code'),
                subscription_tier_id=subscription_tier.id
            )
            db.session.add(org)
            db.session.flush()  # Get the ID
            logger.info(f"Created organization with ID: {org.id} and tier: {tier}")

            # Create organization owner user
            owner_user = User(
                username=pending_signup['username'],
                email=pending_signup['email'],
                first_name=pending_signup['first_name'],
                last_name=pending_signup['last_name'],
                phone=pending_signup.get('phone'),
                organization_id=org.id,
                user_type='customer',
                is_organization_owner=True,
                is_active=True,
                email_verified=pending_signup.get('email_verified', False),
                oauth_provider=pending_signup.get('oauth_provider'),
                oauth_provider_id=pending_signup.get('oauth_provider_id'),
                timezone=pending_signup.get('detected_timezone', 'UTC')  # Auto-detect from browser
            )
            
            # Set password only for non-OAuth users
            if pending_signup.get('password_hash'):
                owner_user.password_hash = pending_signup['password_hash']
            elif pending_signup.get('password'):
                owner_user.set_password(pending_signup['password'])
            
            db.session.add(owner_user)
            db.session.flush()
            logger.info(f"Created user with ID: {owner_user.id}")

            # Assign organization owner role
            org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
            if org_owner_role:
                owner_user.assign_role(org_owner_role)
                logger.info("Assigned organization_owner role")

            # Subscription tracking is now handled by the SubscriptionTier relationship
            # The organization is already assigned to the correct tier above
            db.session.commit()
            logger.info(f"Organization assigned to tier: {tier}")

            # Commit all changes
            db.session.commit()
            logger.info("Database changes committed successfully")

            # Send welcome email
            from ..services.email_service import EmailService
            EmailService.send_welcome_email(
                owner_user.email,
                owner_user.first_name,
                org.name,
                subscription_tier.name
            )

            # Send verification email if needed
            if not owner_user.email_verified:
                owner_user.email_verification_token = EmailService.generate_verification_token(owner_user.email)
                owner_user.email_verification_sent_at = TimezoneUtils.utc_now()
                db.session.commit()
                
                EmailService.send_verification_email(
                    owner_user.email,
                    owner_user.email_verification_token,
                    owner_user.first_name
                )
                
                flash(f'Account created! Please check your email to verify your account before logging in.', 'success')
                # Clear pending signup data
                session.pop('pending_signup', None)
                return redirect(url_for('auth.login'))
            else:
                # OAuth user - log them in immediately
                login_user(owner_user)
                SessionService.rotate_user_session(owner_user)
                owner_user.last_login = TimezoneUtils.utc_now()
                db.session.commit()
                logger.info(f"User {owner_user.username} logged in successfully")

            # Clear pending signup data
            session.pop('pending_signup', None)
            logger.info("Cleared pending signup data from session")

            flash(f'Welcome to BatchTrack! Your {tier.title()} account is ready to use.', 'success')
            return redirect(url_for('app_routes.dashboard'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating account: {str(e)}")
            flash(f'Error creating account: {str(e)}', 'error')
            return redirect(url_for('auth.signup'))

    @staticmethod
    def validate_pending_signup():
        """Validate pending signup data exists and is complete"""
        pending_signup = session.get('pending_signup')
        if not pending_signup:
            return False, "No pending signup found"

        required_fields = ['username', 'email', 'first_name', 'last_name', 'org_name', 'password', 'selected_tier']
        missing_fields = [field for field in required_fields if not pending_signup.get(field)]

        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"

        return True, "Valid signup data"

    @staticmethod
    def complete_stripe_signup(signup_data, tier, stripe_customer_id):
        """Complete signup after successful Stripe payment"""
        logger.info(f"=== STRIPE SIGNUP COMPLETION ===")
        logger.info(f"Processing tier: {tier}")
        logger.info(f"Customer ID: {stripe_customer_id}")
        
        try:
            # Get the subscription tier
            subscription_tier = SubscriptionTier.find_by_identifier(tier)
            if not subscription_tier:
                raise Exception(f"Subscription tier '{tier}' not found")

            # Create organization
            org = Organization(
                name=signup_data['org_name'],
                contact_email=signup_data['email'],
                is_active=True,
                signup_source=signup_data.get('signup_source', 'stripe'),
                promo_code=signup_data.get('promo_code'),
                referral_code=signup_data.get('referral_code'),
                subscription_tier_id=subscription_tier.id
            )
            db.session.add(org)
            db.session.flush()
            logger.info(f"Created organization: {org.id}")

            # Create user with hashed password from metadata
            owner_user = User(
                username=signup_data['username'],
                email=signup_data['email'],
                first_name=signup_data['first_name'],
                last_name=signup_data['last_name'],
                phone=signup_data.get('phone'),
                organization_id=org.id,
                user_type='customer',
                is_organization_owner=True,
                is_active=True,
                timezone=signup_data.get('detected_timezone', 'UTC')  # Auto-detect from browser
            )
            # Use the pre-hashed password from metadata
            owner_user.password_hash = signup_data['password_hash']
            db.session.add(owner_user)
            db.session.flush()
            logger.info(f"Created user: {owner_user.id}")

            # Assign organization owner role
            org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
            if org_owner_role:
                owner_user.assign_role(org_owner_role)

            db.session.commit()
            
            # Log in the user
            from flask_login import login_user
            login_user(owner_user)
            SessionService.rotate_user_session(owner_user)
            owner_user.last_login = TimezoneUtils.utc_now()
            db.session.commit()
            
            logger.info("Stripe signup completed successfully")
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"Stripe signup error: {str(e)}")
            return False

    @staticmethod
    def clear_pending_signup():
        """Clear pending signup data from session"""
        session.pop('pending_signup', None)
        logger.info("Cleared pending signup data from session")

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
        metadata: Optional[dict] = None,
    ) -> PendingSignup:
        """Persist a pending signup row before redirecting the user to Stripe."""
        cleaned_email = (email or "").strip().lower()
        if not cleaned_email:
            raise ValueError("Email is required for pending signup")

        pending = PendingSignup(
            email=cleaned_email,
            phone=(phone or "").strip() or None,
            signup_source=signup_source or 'direct',
            referral_code=(referral_code or "").strip() or None,
            promo_code=(promo_code or "").strip() or None,
            detected_timezone=detected_timezone or None,
            tier_id=tier.id,
            oauth_provider=(oauth_user_info or {}).get('oauth_provider'),
            oauth_provider_id=(oauth_user_info or {}).get('oauth_provider_id'),
            metadata=metadata or {},
        )

        db.session.add(pending)
        db.session.commit()
        logger.info("Created pending signup %s for %s (tier %s)", pending.id, cleaned_email, tier.id)
        return pending

    @staticmethod
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

        if pending_signup.status == 'account_created' and pending_signup.organization_id and pending_signup.user_id:
            logger.info("Pending signup %s already fulfilled", pending_signup.id)
            org = db.session.get(Organization, pending_signup.organization_id)
            user = db.session.get(User, pending_signup.user_id)
            return org, user

        subscription_tier = pending_signup.tier or SubscriptionTier.query.get(pending_signup.tier_id)
        if not subscription_tier:
            raise ValueError(f"Subscription tier {pending_signup.tier_id} not found for pending signup {pending_signup.id}")

        session_metadata = SignupService._object_to_dict(getattr(checkout_session, 'metadata', {}))
        customer_details = SignupService._object_to_dict(getattr(checkout_session, 'customer_details', {}))
        customer_metadata = SignupService._object_to_dict(getattr(customer_obj, 'metadata', {}))

        pending_signup.stripe_checkout_session_id = pending_signup.stripe_checkout_session_id or getattr(checkout_session, 'id', None)
        pending_signup.stripe_customer_id = pending_signup.stripe_customer_id or getattr(customer_obj, 'id', None)
        pending_signup.mark_status('checkout_completed')

        email = SignupService._first_non_empty(
            customer_details.get('email'),
            getattr(customer_obj, 'email', None),
            pending_signup.email,
        )
        if not email:
            raise ValueError("Stripe checkout session missing customer email")

        phone = SignupService._first_non_empty(
            customer_details.get('phone'),
            getattr(customer_obj, 'phone', None),
            pending_signup.phone,
        )

        full_name = SignupService._first_non_empty(
            customer_details.get('name'),
            getattr(customer_obj, 'name', None),
        )
        first_name, last_name = SignupService._split_name(full_name)

        org_name = (
            session_metadata.get('org_name')
            or customer_metadata.get('org_name')
            or pending_signup.metadata.get('org_name') if pending_signup.metadata else None
        )
        if not org_name:
            org_name = f"{first_name or 'New'}'s Workspace"

        username = SignupService._generate_username(email)

        try:
            org = Organization(
                name=org_name,
                contact_email=email,
                is_active=True,
                signup_source=pending_signup.signup_source or 'stripe',
                promo_code=pending_signup.promo_code,
                referral_code=pending_signup.referral_code,
                subscription_tier_id=subscription_tier.id,
                stripe_customer_id=pending_signup.stripe_customer_id,
                billing_status='active',
                subscription_status='active',
            )
            db.session.add(org)
            db.session.flush()

            owner_user = User(
                username=username,
                email=email,
                first_name=first_name or '',
                last_name=last_name or '',
                phone=phone,
                organization_id=org.id,
                user_type='customer',
                is_organization_owner=True,
                is_active=True,
                email_verified=True,
                oauth_provider=pending_signup.oauth_provider,
                oauth_provider_id=pending_signup.oauth_provider_id,
            )
            owner_user.set_password(secrets.token_urlsafe(16))
            owner_user.timezone = pending_signup.detected_timezone or 'UTC'
            db.session.add(owner_user)
            db.session.flush()

            org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
            if org_owner_role:
                owner_user.assign_role(org_owner_role)

            pending_signup.organization_id = org.id
            pending_signup.user_id = owner_user.id
            pending_signup.mark_status('account_created')

            # Prepare password setup + welcome email tokens
            reset_token = EmailService.generate_reset_token(owner_user.id)
            owner_user.password_reset_token = reset_token
            owner_user.password_reset_sent_at = TimezoneUtils.utc_now()

            db.session.commit()

            try:
                EmailService.send_welcome_email(owner_user.email, owner_user.first_name or owner_user.username, org.name, subscription_tier.name)
            except Exception as email_error:
                logger.warning("Failed to send welcome email: %s", email_error)

            try:
                EmailService.send_password_setup_email(owner_user.email, reset_token, owner_user.first_name or owner_user.username)
            except Exception as email_error:
                logger.warning("Failed to send password setup email: %s", email_error)

            try:
                from .billing_service import BillingService as _BillingService
                _BillingService.invalidate_organization_cache(org.id)
            except Exception:
                pass

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

            return org, owner_user

        except Exception as exc:
            db.session.rollback()
            logger.error("Failed to complete pending signup %s: %s", pending_signup.id, exc)
            fresh = db.session.get(PendingSignup, pending_signup.id)
            if fresh:
                fresh.mark_status('failed', error=str(exc))
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
            if isinstance(value, str) and value.strip() == '':
                continue
            return value
        return None

    @staticmethod
    def _split_name(full_name: Optional[str]) -> Tuple[str, str]:
        if not full_name:
            return '', ''
        parts = full_name.strip().split()
        if not parts:
            return full_name, ''
        if len(parts) == 1:
            return parts[0], ''
        return parts[0], ' '.join(parts[1:])

    @staticmethod
    def _generate_username(email: str) -> str:
        base = (email or 'user').split('@')[0]
        base = ''.join(ch for ch in base if ch.isalnum()) or 'user'
        candidate = base
        counter = 1
        while User.query.filter_by(username=candidate).first():
            candidate = f"{base}{counter}"
            counter += 1
        return candidate
