
import logging
from flask import session, flash, current_app, redirect, url_for
from flask_login import login_user
from ..models import db, User, Organization, Role, SubscriptionTier
from ..utils.timezone_utils import TimezoneUtils
from .session_service import SessionService
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
            # tier is expected to be a DB id as string
            try:
                tier_id = int(tier)
            except (TypeError, ValueError):
                tier_id = None
            subscription_tier = SubscriptionTier.query.get(tier_id) if tier_id is not None else None
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
            subscription_tier = SubscriptionTier.query.filter_by(key=tier).first()
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
