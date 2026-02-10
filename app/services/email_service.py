import logging
from flask import current_app, render_template, url_for
from flask_mail import Message
from ..extensions import mail
from ..utils.timezone_utils import TimezoneUtils
import secrets
import hashlib
from typing import Optional

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
            raw_expiry = current_app.config.get('PASSWORD_RESET_TOKEN_EXPIRY_HOURS', 24)
            try:
                expiry_hours = max(1, int(raw_expiry))
            except (TypeError, ValueError):
                expiry_hours = 24
            expiry_label = "hour" if expiry_hours == 1 else "hours"

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
            <p>This link will expire in {expiry_hours} {expiry_label}.</p>
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
    def _send_email(recipient: str, subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
        """Internal method to send email via configured provider (SMTP default)."""
        provider = (current_app.config.get('EMAIL_PROVIDER') or 'smtp').lower()

        # Route to provider-specific adapter; fallback to SMTP on failure
        try:
            if provider == 'sendgrid':
                if EmailService._send_via_sendgrid(recipient, subject, html_body, text_body):
                    return True
                logger.warning("SendGrid send failed or not configured, falling back to SMTP")
            elif provider == 'postmark':
                if EmailService._send_via_postmark(recipient, subject, html_body, text_body):
                    return True
                logger.warning("Postmark send failed or not configured, falling back to SMTP")
            elif provider == 'mailgun':
                if EmailService._send_via_mailgun(recipient, subject, html_body, text_body):
                    return True
                logger.warning("Mailgun send failed or not configured, falling back to SMTP")
            # 'ses' typically uses SMTP; if SES-specific SDK not configured, just use SMTP config
        except Exception as e:
            logger.warning(f"Provider adapter error ({provider}): {e}; falling back to SMTP")

        # SMTP default path via Flask-Mail
        try:
            default_sender = current_app.config.get('MAIL_DEFAULT_SENDER')
            msg = Message(
                subject=subject,
                recipients=[recipient],
                html=html_body,
                body=text_body,
                sender=default_sender
            )
            mail.send(msg)
            logger.info(f"Email sent successfully to {recipient} via SMTP")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {recipient} (SMTP): {str(e)}")
            return False

    @staticmethod
    def _send_via_sendgrid(recipient: str, subject: str, html_body: str, text_body: Optional[str]) -> bool:
        api_key = current_app.config.get('SENDGRID_API_KEY')
        from_email = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('DEFAULT_FROM_EMAIL')
        if not api_key or not from_email:
            return False
        try:
            import requests
            payload = {
                'personalizations': [{ 'to': [{ 'email': recipient }] }],
                'from': { 'email': from_email },
                'subject': subject,
                'content': [
                    { 'type': 'text/plain', 'value': text_body or '' },
                    { 'type': 'text/html', 'value': html_body or '' }
                ]
            }
            headers = { 'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json' }
            resp = requests.post('https://api.sendgrid.com/v3/mail/send', json=payload, headers=headers, timeout=10)
            if 200 <= resp.status_code < 300:
                logger.info(f"Email sent to {recipient} via SendGrid")
                return True
            logger.error(f"SendGrid error {resp.status_code}: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"SendGrid send error: {e}")
            return False

    @staticmethod
    def _send_via_postmark(recipient: str, subject: str, html_body: str, text_body: Optional[str]) -> bool:
        server_token = current_app.config.get('POSTMARK_SERVER_TOKEN')
        from_email = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('DEFAULT_FROM_EMAIL')
        if not server_token or not from_email:
            return False
        try:
            import requests
            payload = {
                'From': from_email,
                'To': recipient,
                'Subject': subject,
                'TextBody': text_body or '',
                'HtmlBody': html_body or ''
            }
            headers = { 'X-Postmark-Server-Token': server_token }
            resp = requests.post('https://api.postmarkapp.com/email', json=payload, headers=headers, timeout=10)
            if 200 <= resp.status_code < 300:
                logger.info(f"Email sent to {recipient} via Postmark")
                return True
            logger.error(f"Postmark error {resp.status_code}: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"Postmark send error: {e}")
            return False

    @staticmethod
    def _send_via_mailgun(recipient: str, subject: str, html_body: str, text_body: Optional[str]) -> bool:
        api_key = current_app.config.get('MAILGUN_API_KEY')
        domain = current_app.config.get('MAILGUN_DOMAIN')
        from_email = current_app.config.get('MAIL_DEFAULT_SENDER') or f"postmaster@{domain}" if domain else None
        if not api_key or not domain or not from_email:
            return False
        try:
            import requests
            data = {
                'from': from_email,
                'to': [recipient],
                'subject': subject,
                'text': text_body or '',
                'html': html_body or ''
            }
            resp = requests.post(f'https://api.mailgun.net/v3/{domain}/messages', auth=('api', api_key), data=data, timeout=10)
            if 200 <= resp.status_code < 300:
                logger.info(f"Email sent to {recipient} via Mailgun")
                return True
            logger.error(f"Mailgun error {resp.status_code}: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"Mailgun send error: {e}")
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

        subject = "Finish setting your BatchTrack password"
        reset_url = url_for('auth.reset_password', token=token, _external=True)

        body = f"""
        Hi {first_name},

        Thanks for joining BatchTrack! If you haven’t finished creating a password on the welcome screen yet, you can do it now by clicking the link below:
        {reset_url}

        This link will expire in 24 hours. If you’ve already set your password in the app, feel free to ignore this message.

        We’re excited to have you onboard!
        The BatchTrack Team
        """

        return EmailService._send_email(email, subject, body)

    @staticmethod
    def is_configured():
        """Check if email is properly configured for the selected provider."""
        try:
            provider = (current_app.config.get('EMAIL_PROVIDER') or 'smtp').lower()
            if provider == 'sendgrid':
                return bool(current_app.config.get('SENDGRID_API_KEY'))
            if provider == 'postmark':
                return bool(current_app.config.get('POSTMARK_SERVER_TOKEN'))
            if provider == 'mailgun':
                return bool(current_app.config.get('MAILGUN_API_KEY') and current_app.config.get('MAILGUN_DOMAIN'))
            # SES SMTP or generic SMTP
            mail_server = current_app.config.get('MAIL_SERVER')
            default_sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('DEFAULT_FROM_EMAIL')
            if not mail_server or not default_sender:
                return False
            if current_app.config.get('EMAIL_SMTP_ALLOW_NO_AUTH'):
                return True
            return bool(current_app.config.get('MAIL_USERNAME') and current_app.config.get('MAIL_PASSWORD'))
        except Exception:
            return False

    @staticmethod
    def get_verification_mode() -> str:
        """Resolve effective verification mode from config and provider readiness."""
        raw_mode = (current_app.config.get('AUTH_EMAIL_VERIFICATION_MODE') or 'prompt').strip().lower()
        mode = raw_mode if raw_mode in {'off', 'prompt', 'required'} else 'prompt'

        require_provider = bool(current_app.config.get('AUTH_EMAIL_REQUIRE_PROVIDER', True))
        if mode != 'off' and require_provider and not EmailService.is_configured():
            return 'off'
        return mode

    @staticmethod
    def should_issue_verification_tokens() -> bool:
        """Whether account flows should create and send verification links."""
        return EmailService.get_verification_mode() in {'prompt', 'required'}

    @staticmethod
    def should_require_verified_email_on_login() -> bool:
        """Whether login should block unverified users."""
        return EmailService.get_verification_mode() == 'required'

    @staticmethod
    def password_reset_enabled() -> bool:
        """Whether forgot/reset-by-email should be active for this environment."""
        if not current_app.config.get('AUTH_PASSWORD_RESET_ENABLED', True):
            return False
        require_provider = bool(current_app.config.get('AUTH_EMAIL_REQUIRE_PROVIDER', True))
        if require_provider and not EmailService.is_configured():
            return False
        return True

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