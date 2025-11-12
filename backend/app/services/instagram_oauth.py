"""
Instagram OAuth service for connecting accounts and managing access tokens.

This service handles the OAuth 2.0 flow for Instagram Basic Display API:
1. Generate authorization URL
2. Exchange authorization code for access token
3. Refresh expired tokens
4. Fetch user profile information
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.parse import urlencode
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.models import SocialAccount, PlatformType


class InstagramOAuthError(Exception):
    """Raised when Instagram OAuth operations fail."""
    pass


class InstagramOAuthService:
    """
    Service for Instagram OAuth operations.

    Instagram OAuth Flow:
    1. User clicks "Connect Instagram"
    2. Redirect to Instagram with authorization URL
    3. User approves permissions
    4. Instagram redirects back with authorization code
    5. Exchange code for access token
    6. Store token and user info in database
    """

    def __init__(self):
        self.client_id = settings.INSTAGRAM_CLIENT_ID
        self.client_secret = settings.INSTAGRAM_CLIENT_SECRET
        self.redirect_uri = settings.INSTAGRAM_REDIRECT_URI
        self.base_url = "https://api.instagram.com"
        self.graph_api_url = "https://graph.instagram.com"

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate Instagram authorization URL to redirect user to.

        Args:
            state: Optional CSRF protection token (recommended in production)

        Returns:
            Full authorization URL to redirect user to

        Example:
            url = service.get_authorization_url(state="random_token_123")
            # Returns: https://api.instagram.com/oauth/authorize?client_id=...
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user_profile,user_media",  # Basic permissions
            "response_type": "code",
        }

        if state:
            params["state"] = state

        return f"{self.base_url}/oauth/authorize?{urlencode(params)}"

    async def exchange_code_for_token(
        self, code: str
    ) -> Dict[str, any]:
        """
        Exchange authorization code for access token.

        This is step 2 of the OAuth flow, called after user approves permissions.

        Args:
            code: Authorization code from Instagram callback

        Returns:
            Dictionary containing:
            - access_token: Long-lived access token
            - user_id: Instagram user ID
            - expires_in: Token expiration time in seconds (default: 60 days)

        Raises:
            InstagramOAuthError: If token exchange fails
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/oauth/access_token",
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "authorization_code",
                        "redirect_uri": self.redirect_uri,
                        "code": code,
                    },
                )
                response.raise_for_status()
                data = response.json()

                # Exchange short-lived token for long-lived token
                long_lived = await self._exchange_for_long_lived_token(
                    data["access_token"]
                )

                return long_lived

            except httpx.HTTPStatusError as e:
                raise InstagramOAuthError(
                    f"Failed to exchange code for token: {e.response.text}"
                )
            except Exception as e:
                raise InstagramOAuthError(f"OAuth error: {str(e)}")

    async def _exchange_for_long_lived_token(
        self, short_lived_token: str
    ) -> Dict[str, any]:
        """
        Exchange short-lived token (1 hour) for long-lived token (60 days).

        Instagram returns short-lived tokens by default. We immediately
        exchange them for long-lived tokens that last 60 days.

        Args:
            short_lived_token: Token from initial OAuth exchange

        Returns:
            Dictionary with access_token, token_type, and expires_in
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.graph_api_url}/access_token",
                    params={
                        "grant_type": "ig_exchange_token",
                        "client_secret": self.client_secret,
                        "access_token": short_lived_token,
                    },
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                raise InstagramOAuthError(
                    f"Failed to get long-lived token: {e.response.text}"
                )

    async def refresh_access_token(self, current_token: str) -> Dict[str, any]:
        """
        Refresh a long-lived access token before it expires.

        Long-lived tokens expire after 60 days but can be refreshed if:
        - Token is at least 24 hours old
        - Token hasn't expired yet

        Args:
            current_token: Existing long-lived access token

        Returns:
            Dictionary with new access_token and expires_in

        Raises:
            InstagramOAuthError: If refresh fails
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.graph_api_url}/refresh_access_token",
                    params={
                        "grant_type": "ig_refresh_token",
                        "access_token": current_token,
                    },
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                raise InstagramOAuthError(
                    f"Failed to refresh token: {e.response.text}"
                )

    async def get_user_profile(self, access_token: str) -> Dict[str, any]:
        """
        Fetch user profile information from Instagram.

        Args:
            access_token: Valid Instagram access token

        Returns:
            Dictionary containing:
            - id: Instagram user ID
            - username: Instagram username
            - account_type: BUSINESS, CREATOR, or PERSONAL
            - media_count: Number of media items

        Raises:
            InstagramOAuthError: If profile fetch fails
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.graph_api_url}/me",
                    params={
                        "fields": "id,username,account_type,media_count",
                        "access_token": access_token,
                    },
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                raise InstagramOAuthError(
                    f"Failed to fetch profile: {e.response.text}"
                )

    async def save_account(
        self,
        db: Session,
        access_token: str,
        user_id: str,
        expires_in: int,
        username: Optional[str] = None,
    ) -> SocialAccount:
        """
        Save or update Instagram account in database.

        Args:
            db: Database session
            access_token: Instagram access token
            user_id: Instagram user ID
            expires_in: Token expiration time in seconds
            username: Optional username to store

        Returns:
            SocialAccount instance
        """
        # Check if account already exists
        existing = (
            db.query(SocialAccount)
            .filter(
                SocialAccount.platform == PlatformType.INSTAGRAM,
                SocialAccount.account_id == user_id,
            )
            .first()
        )

        token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        if existing:
            # Update existing account
            existing.access_token = access_token
            existing.token_expires_at = token_expires_at
            existing.username = username or existing.username
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing
        else:
            # Create new account
            account = SocialAccount(
                platform=PlatformType.INSTAGRAM,
                account_id=user_id,
                username=username,
                access_token=access_token,
                token_expires_at=token_expires_at,
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            return account

    async def ensure_valid_token(
        self, db: Session, account: SocialAccount
    ) -> str:
        """
        Ensure account has a valid access token, refreshing if needed.

        This should be called before making any Instagram API requests.

        Args:
            db: Database session
            account: SocialAccount instance

        Returns:
            Valid access token

        Raises:
            InstagramOAuthError: If token refresh fails
        """
        # Check if token is expired or expiring soon (within 7 days)
        if account.token_expires_at:
            days_until_expiry = (
                account.token_expires_at - datetime.utcnow()
            ).days

            if days_until_expiry < 7:
                # Refresh token
                refresh_data = await self.refresh_access_token(
                    account.access_token
                )

                account.access_token = refresh_data["access_token"]
                account.token_expires_at = datetime.utcnow() + timedelta(
                    seconds=refresh_data["expires_in"]
                )
                account.updated_at = datetime.utcnow()
                db.commit()

        return account.access_token


# Singleton instance
instagram_oauth_service = InstagramOAuthService()
