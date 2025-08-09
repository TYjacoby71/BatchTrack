import logging
from flask import current_app, render_template, url_for
from flask_mail import Message
from ..extensions import mail
from ..utils.timezone_utils import TimezoneUtils
import secrets
import hashlib

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails"""

    @staticmethod
    def send_verification_email(email, verification_token, user_name=None):
        """Send email verification link"""
        try:
            verification_url = url_for('auth.verify_email', 
                                     token=verification_token, 
                                     _external=True)

            subject = "Verify your BatchTrack account"

            html_body = f"""
            <h2>Welcome to BatchTrack!</h2>
            <p>Hi {user_name or 'there'},</p>
            <p>Thank you for signing up for BatchTrack. Please verify your email address by clicking the link below:</p>
            <p><a href="{verification_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Email Address</a></p>
            <p>If the button doesn't work, copy and paste this link into your browser:</p>
            <p>{verification_url}</p>
            <p>This link will expire in 24 hours.</p>
            <p>If you didn't create an account with BatchTrack, please ignore this email.</p>
            <br>
            <p>Best regards,<br>The BatchTrack Team</p>
            """

            text_body = f"""
            Welcome to BatchTrack!

            Hi {user_name or 'there'},

            Thank you for signing up for BatchTrack. Please verify your email address by visiting:
            {verification_url}

            This link will expire in 24 hours.

            If you didn't create an account with BatchTrack, please ignore this email.

            Best regards,
            The BatchTrack Team
            """

            return EmailService._send_email(
                recipient=email,
                subject=subject,
                html_body=html_body,
                text_body=text_body
            )

        except Exception as e:
            logger.error(f"Error sending verification email: {str(e)}")
            return False

    @staticmethod
    def send_welcome_email(user_email, user_name, organization_name, tier_name):
        """Send welcome email after successful signup"""
        try:
            subject = f"Welcome to BatchTrack - Your {tier_name} account is ready!"

            dashboard_url = url_for('app_routes.dashboard', _external=True)

            html_body = f"""
            <h2>Welcome to BatchTrack, {user_name}!</h2>
            <p>Your {tier_name} account for <strong>{organization_name}</strong> has been successfully created and is ready to use.</p>

            <h3>Getting Started:</h3>
            <ul>
                <li><a href="{dashboard_url}">Access your dashboard</a></li>
                <li>Set up your first ingredients and recipes</li>
                <li>Start tracking your production batches</li>
                <li>Manage your inventory with FIFO tracking</li>
            </ul>

            <p>Need help? Check out our documentation or contact support.</p>

            <p><a href="{dashboard_url}" style="background-color: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px;">Go to Dashboard</a></p>

            <br>
            <p>Happy making!<br>The BatchTrack Team</p>
            """

            return EmailService._send_email(
                recipient=user_email,
                subject=subject,
                html_body=html_body
            )

        except Exception as e:
            logger.error(f"Error sending welcome email: {str(e)}")
            return False

    @staticmethod
    def send_password_reset_email(user_email, reset_token, user_name=None):
        """Send password reset email"""
        try:
            reset_url = url_for('auth.reset_password', 
                              token=reset_token, 
                              _external=True)

            subject = "Reset your BatchTrack password"

            html_body = f"""
            <h2>Password Reset Request</h2>
            <p>Hi {user_name or 'there'},</p>
            <p>You requested a password reset for your BatchTrack account. Click the link below to set a new password:</p>
            <p><a href="{reset_url}" style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
            <p>If the button doesn't work, copy and paste this link into your browser:</p>
            <p>{reset_url}</p>
            <p>This link will expire in 1 hour.</p>
            <p>If you didn't request this reset, please ignore this email.</p>
            <br>
            <p>Best regards,<br>The BatchTrack Team</p>
            """

            return EmailService._send_email(
                recipient=user_email,
                subject=subject,
                html_body=html_body
            )

        except Exception as e:
            logger.error(f"Error sending password reset email: {str(e)}")
            return False

    @staticmethod
    def _send_email(recipient, subject, html_body, text_body=None):
        """Internal method to send email"""
        try:
            msg = Message(
                subject=subject,
                recipients=[recipient],
                html=html_body,
                body=text_body
            )

            mail.send(msg)
            logger.info(f"Email sent successfully to {recipient}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {str(e)}")
            return False

    @staticmethod
    def generate_verification_token(email):
        """Generate a secure verification token"""
        timestamp = str(TimezoneUtils.utc_now().timestamp())
        data = f"{email}:{timestamp}:{secrets.token_hex(16)}"
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def generate_reset_token(user_id):
        """Generate a secure password reset token"""
        timestamp = str(TimezoneUtils.utc_now().timestamp())
        data = f"{user_id}:{timestamp}:{secrets.token_hex(16)}"
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def send_password_setup_email(email, token, first_name):
        """Send password setup email for new accounts"""
        if not EmailService.is_configured():
            print(f"Email not configured - would send password setup to {email}")
            return False

        subject = "Set up your BatchTrack password"
        reset_url = url_for('auth.reset_password', token=token, _external=True)

        body = f"""
        Hi {first_name},

        Welcome to BatchTrack! Your account has been created successfully.

        To complete your setup, please create a password by clicking the link below:
        {reset_url}

        This link will expire in 24 hours.

        Best regards,
        The BatchTrack Team
        """

        return EmailService._send_email(email, subject, body)

    @staticmethod
    def is_configured():
        """Check if email is properly configured"""
        try:
            return (current_app.config.get('MAIL_SERVER') and 
                   current_app.config.get('MAIL_USERNAME'))
        except:
            return False

    @staticmethod
    def send_waitlist_confirmation(email, first_name=None, last_name=None, name=None):
        """Send waitlist confirmation email"""
        if not EmailService.is_configured():
            logger.info(f"Email not configured - would send waitlist confirmation to {email}")
            return False

        try:
            subject = "Welcome to the BatchTrack Waitlist!"

            # Build personalized greeting - prefer first_name over legacy name field
            if first_name:
                greeting = f"Hi {first_name},"
            elif name:
                greeting = f"Hi {name},"
            else:
                greeting = "Hi there,"

            html_body = f"""
            <h2>Thanks for joining our waitlist!</h2>
            <p>{greeting}</p>
            <p>Thank you for your interest in BatchTrack! You're now on our exclusive waitlist.</p>

            <h3>What's Next?</h3>
            <ul>
                <li>We'll notify you as soon as BatchTrack is ready for beta testing</li>
                <li>You'll get early access to special pricing and lifetime deals</li>
                <li>We'll keep you updated on our development progress</li>
            </ul>

            <p>In the meantime, feel free to reach out if you have any questions about BatchTrack.</p>

            <br>
            <p>Thanks again for your interest!<br>The BatchTrack Team</p>
            """

            text_body = f"""
            Thanks for joining our waitlist!

            {greeting}

            Thank you for your interest in BatchTrack! You're now on our exclusive waitlist.

            What's Next?
            - We'll notify you as soon as BatchTrack is ready for beta testing
            - You'll get early access to special pricing and lifetime deals  
            - We'll keep you updated on our development progress

            In the meantime, feel free to reach out if you have any questions about BatchTrack.

            Thanks again for your interest!
            The BatchTrack Team
            """

            return EmailService._send_email(
                recipient=email,
                subject=subject,
                html_body=html_body,
                text_body=text_body
            )

        except Exception as e:
            logger.error(f"Error sending waitlist confirmation email: {str(e)}")
            return False