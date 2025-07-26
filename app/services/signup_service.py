
import logging
from flask import session, flash, current_app, redirect, url_for
from flask_login import login_user
from ..models import db, User, Organization, Role, Subscription
from ..blueprints.developer.subscription_tiers import load_tiers_config
from .stripe_service import StripeService

logger = logging.getLogger(__name__)

class SignupService:
    """Service for handling complete signup and organization creation"""

    @staticmethod
    def complete_signup(tier, is_stripe_mode=False):
        """Complete organization creation and user signup"""
        logger.info(f"=== SIGNUP COMPLETION START ===")
        logger.info(f"Requested tier: {tier}")
        logger.info(f"Stripe mode: {is_stripe_mode}")

        if is_stripe_mode:
            flash('Processing payment and creating account...', 'info')
        else:
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

        # Double-check tier configuration before proceeding
        tiers_config = load_tiers_config()
        tier_data = tiers_config.get(tier, {})
        is_stripe_ready = tier_data.get('is_stripe_ready', False)
        logger.info(f"Final tier check - Stripe ready: {is_stripe_ready}, should match stripe_mode: {is_stripe_mode}")

        try:
            # Create organization
            org = Organization(
                name=pending_signup['org_name'],
                contact_email=pending_signup['email'],
                is_active=True,
                signup_source=pending_signup['signup_source'],
                promo_code=pending_signup.get('promo_code'),
                referral_code=pending_signup.get('referral_code')
            )
            db.session.add(org)
            db.session.flush()  # Get the ID
            logger.info(f"Created organization with ID: {org.id}")

            # Create subscription record
            subscription = Subscription(
                organization_id=org.id,
                tier=tier,
                status='active',
                notes=f"Created from signup for {tier} tier ({'Stripe' if is_stripe_mode else 'development'} mode)"
            )
            db.session.add(subscription)
            db.session.flush()
            logger.info(f"Created subscription with tier: {tier}")

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
                is_active=True
            )
            owner_user.set_password(pending_signup['password'])
            db.session.add(owner_user)
            db.session.flush()
            logger.info(f"Created user with ID: {owner_user.id}")

            # Assign organization owner role
            org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
            if org_owner_role:
                owner_user.assign_role(org_owner_role)
                logger.info("Assigned organization_owner role")

            # For development mode, activate subscription
            if not is_stripe_mode:
                success = StripeService.simulate_subscription_success(org, tier)
                if not success:
                    raise Exception("Failed to activate development subscription")
                logger.info("Activated development subscription")

            # Commit all changes
            db.session.commit()
            logger.info("Database changes committed successfully")

            # Log in the user
            login_user(owner_user)
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
    def clear_pending_signup():
        """Clear pending signup data from session"""
        session.pop('pending_signup', None)
        logger.info("Cleared pending signup data from session")
