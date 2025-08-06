
import logging
from flask import current_app, session, url_for, request
import google_auth_oauthlib.flow
import google.auth.transport.requests
import google.oauth2.credentials
import requests
import json

logger = logging.getLogger(__name__)

class OAuthService:
    """Service for handling OAuth authentication"""

    @staticmethod
    def create_google_oauth_flow():
        """Create Google OAuth flow"""
        try:
            # Check if OAuth is configured first
            if not OAuthService.is_oauth_configured():
                logger.warning("OAuth not configured - missing client ID or secret")
                return None
                
            client_id = current_app.config.get('GOOGLE_OAUTH_CLIENT_ID')
            client_secret = current_app.config.get('GOOGLE_OAUTH_CLIENT_SECRET')
            
            if not client_id or not client_secret:
                logger.error("Missing OAuth credentials")
                return None
            
            # OAuth configuration
            client_config = {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [url_for('auth.oauth_callback', _external=True)]
                }
            }

            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config,
                scopes=[
                    "https://www.googleapis.com/auth/userinfo.email",
                    "https://www.googleapis.com/auth/userinfo.profile",
                    "openid"
                ]
            )

            # Set redirect URI
            flow.redirect_uri = url_for('auth.oauth_callback', _external=True)
            
            logger.info("OAuth flow created successfully")
            return flow
            
        except Exception as e:
            logger.error(f"Error creating OAuth flow: {str(e)}")
            return None

    @staticmethod
    def get_authorization_url():
        """Get Google authorization URL"""
        try:
            flow = OAuthService.create_google_oauth_flow()
            if not flow:
                return None, None

            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )

            return authorization_url, state
            
        except Exception as e:
            logger.error(f"Error getting authorization URL: {str(e)}")
            return None, None

    @staticmethod
    def exchange_code_for_token(authorization_code, state):
        """Exchange authorization code for access token"""
        try:
            flow = OAuthService.create_google_oauth_flow()
            if not flow:
                return None

            # Verify state
            if not session.get('oauth_state') == state:
                logger.error("OAuth state mismatch")
                return None

            # Exchange code for token
            flow.fetch_token(authorization_response=request.url)
            
            return flow.credentials
            
        except Exception as e:
            logger.error(f"Error exchanging code for token: {str(e)}")
            return None

    @staticmethod
    def get_user_info(credentials):
        """Get user information from Google"""
        try:
            # Use the credentials to get user info
            response = requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {credentials.token}"}
            )

            if response.status_code == 200:
                user_info = response.json()
                logger.info(f"Retrieved user info for: {user_info.get('email')}")
                return user_info
            else:
                logger.error(f"Failed to get user info: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting user info: {str(e)}")
            return None

    @staticmethod
    def is_oauth_configured():
        """Check if OAuth is properly configured"""
        client_id = current_app.config.get('GOOGLE_OAUTH_CLIENT_ID')
        client_secret = current_app.config.get('GOOGLE_OAUTH_CLIENT_SECRET')
        
        configured = bool(client_id and client_secret)
        
        if not configured:
            logger.debug(f"OAuth configuration check: Client ID present: {bool(client_id)}, Client Secret present: {bool(client_secret)}")
        else:
            logger.debug("OAuth is properly configured")
            
        return configured
        
    @staticmethod
    def get_configuration_status():
        """Get detailed OAuth configuration status for debugging"""
        client_id = current_app.config.get('GOOGLE_OAUTH_CLIENT_ID')
        client_secret = current_app.config.get('GOOGLE_OAUTH_CLIENT_SECRET')
        
        return {
            'is_configured': bool(client_id and client_secret),
            'has_client_id': bool(client_id),
            'has_client_secret': bool(client_secret),
            'client_id_length': len(client_id) if client_id else 0,
            'client_secret_length': len(client_secret) if client_secret else 0
        }
