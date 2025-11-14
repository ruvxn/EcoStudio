"""
Instagram OAuth service for connecting accounts and managing access tokens.

This service handles the OAuth 2.0 flow for Instagram Basic Display API:
1. Generate authorization URL
2. Exchange authorization code for access token
3. Refresh expired tokens
4. Fetch user profile information
"""
from datetime import datetime, timedelta, timezone
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
        # Use Facebook OAuth for Instagram Graph API (Business)
        self.base_url = "https://www.facebook.com"
        self.graph_api_url = "https://graph.facebook.com"
        self.graph_api_version = "v21.0"

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate Instagram authorization URL using Facebook Login for Business.

        For Instagram Graph API (Business), we use Facebook's OAuth endpoints.

        Args:
            state: Optional CSRF protection token (recommended in production)

        Returns:
            Full authorization URL to redirect user to

        Example:
            url = service.get_authorization_url(state="random_token_123")
            # Returns: https://www.facebook.com/v21.0/dialog/oauth?...
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            # Instagram Graph API permissions
            "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,pages_manage_metadata",
            "response_type": "code",
        }

        if state:
            params["state"] = state

        return f"{self.base_url}/{self.graph_api_version}/dialog/oauth?{urlencode(params)}"

    async def exchange_code_for_token(
        self, code: str
    ) -> Dict[str, any]:
        """
        Exchange authorization code for access token using Facebook Graph API.

        This is step 2 of the OAuth flow, called after user approves permissions.

        Args:
            code: Authorization code from Facebook callback

        Returns:
            Dictionary containing:
            - access_token: Access token (for Facebook/Instagram)
            - token_type: Token type
            - expires_in: Token expiration time in seconds

        Raises:
            InstagramOAuthError: If token exchange fails
        """
        async with httpx.AsyncClient() as client:
            try:
                # Exchange code for short-lived Facebook token
                response = await client.get(
                    f"{self.graph_api_url}/{self.graph_api_version}/oauth/access_token",
                    params={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
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

        Facebook returns short-lived tokens by default. We immediately
        exchange them for long-lived tokens that last 60 days.

        Args:
            short_lived_token: Token from initial OAuth exchange

        Returns:
            Dictionary with access_token, token_type, and expires_in
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.graph_api_url}/{self.graph_api_version}/oauth/access_token",
                    params={
                        "grant_type": "fb_exchange_token",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "fb_exchange_token": short_lived_token,
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
        Fetch Instagram business account information via Facebook Graph API.

        For Instagram Graph API, we need to:
        1. Get user's Facebook pages (or use fallback page ID for dev mode)
        2. Get Instagram business account connected to a page
        3. Get Instagram account details

        Args:
            access_token: Valid Facebook access token

        Returns:
            Dictionary containing:
            - id: Instagram business account ID
            - username: Instagram username
            - name: Account name
            - profile_picture_url: Profile picture URL

        Raises:
            InstagramOAuthError: If profile fetch fails
        """
        async with httpx.AsyncClient() as client:
            try:
                import logging
                logger = logging.getLogger(__name__)

                page_id = None

                # Step 1: Try to get user's Facebook pages
                try:
                    pages_response = await client.get(
                        f"{self.graph_api_url}/{self.graph_api_version}/me/accounts",
                        params={
                            "access_token": access_token,
                        },
                    )
                    pages_response.raise_for_status()
                    pages_data = pages_response.json()
                    logger.info(f"DEBUG: /me/accounts response: {pages_data}")

                    if pages_data.get("data"):
                        # Use first page from /me/accounts
                        page = pages_data["data"][0]
                        page_id = page["id"]
                        logger.info(f"DEBUG: Using page from /me/accounts: {page_id}")
                except Exception as e:
                    logger.warning(f"DEBUG: /me/accounts failed or empty: {e}")

                # Fallback: If /me/accounts is empty (common in dev mode), try direct page access
                if not page_id:
                    fallback_page_id = settings.INSTAGRAM_FALLBACK_PAGE_ID
                    if not fallback_page_id:
                        raise InstagramOAuthError(
                            "No Facebook pages found via /me/accounts and INSTAGRAM_FALLBACK_PAGE_ID not set. "
                            "In development mode, set INSTAGRAM_FALLBACK_PAGE_ID in your .env file."
                        )
                    logger.info(f"DEBUG: /me/accounts empty, trying fallback page ID: {fallback_page_id}")

                    # Verify we can access this page
                    try:
                        page_check = await client.get(
                            f"{self.graph_api_url}/{self.graph_api_version}/{fallback_page_id}",
                            params={
                                "fields": "id,name,instagram_business_account",
                                "access_token": access_token,
                            },
                        )
                        page_check.raise_for_status()
                        page_data = page_check.json()
                        logger.info(f"DEBUG: Fallback page access successful: {page_data}")
                        page_id = fallback_page_id
                    except httpx.HTTPStatusError as e:
                        logger.error(f"DEBUG: Fallback page access failed: {e.response.text}")
                        raise InstagramOAuthError(
                            "No Facebook pages found via /me/accounts and fallback page access failed. "
                            "This usually happens in development mode. Please ensure:\n"
                            "1. You are added as a Developer/Admin in the Facebook App settings\n"
                            "2. Your Facebook page is connected to your Instagram business account\n"
                            "3. The app has the required permissions: pages_show_list, instagram_basic"
                        )

                if not page_id:
                    raise InstagramOAuthError(
                        "Could not determine Facebook page ID. Please check your app configuration."
                    )

                # Step 2: Get Instagram account for the page
                ig_account_response = await client.get(
                    f"{self.graph_api_url}/{self.graph_api_version}/{page_id}",
                    params={
                        "fields": "instagram_business_account",
                        "access_token": access_token,
                    },
                )
                ig_account_response.raise_for_status()
                ig_data = ig_account_response.json()
                logger.info(f"DEBUG: Instagram account lookup: {ig_data}")

                if "instagram_business_account" not in ig_data:
                    raise InstagramOAuthError(
                        f"No Instagram business account connected to Facebook page (ID: {page_id}). "
                        "Please connect an Instagram business account to your Facebook page."
                    )

                ig_account_id = ig_data["instagram_business_account"]["id"]
                logger.info(f"DEBUG: Instagram Business Account ID: {ig_account_id}")

                # Step 3: Get Instagram account details
                profile_response = await client.get(
                    f"{self.graph_api_url}/{self.graph_api_version}/{ig_account_id}",
                    params={
                        "fields": "id,username,name,profile_picture_url,followers_count,media_count",
                        "access_token": access_token,
                    },
                )
                profile_response.raise_for_status()
                profile_data = profile_response.json()
                logger.info(f"DEBUG: Instagram profile: {profile_data}")
                return profile_data

            except httpx.HTTPStatusError as e:
                raise InstagramOAuthError(
                    f"Failed to fetch profile: {e.response.text}"
                )
            except KeyError as e:
                raise InstagramOAuthError(
                    f"Unexpected response format: missing field {str(e)}"
                )

    async def save_account(
        self,
        db: Session,
        access_token: str,
        user_id: str,
        expires_in: int,
        username: Optional[str] = None,
        follower_count: Optional[int] = None,
    ) -> SocialAccount:
        """
        Save or update Instagram account in database.

        Args:
            db: Database session
            access_token: Instagram/Facebook access token
            user_id: Instagram business account ID
            expires_in: Token expiration time in seconds
            username: Optional username to store
            follower_count: Optional follower count

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

        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        if existing:
            # Update existing account
            existing.access_token = access_token
            existing.token_expires_at = token_expires_at
            existing.username = username or existing.username
            existing.follower_count = follower_count or existing.follower_count
            existing.updated_at = datetime.now(timezone.utc)
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
                follower_count=follower_count,
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
                account.token_expires_at - datetime.now(timezone.utc)
            ).days

            if days_until_expiry < 7:
                # Refresh token
                refresh_data = await self.refresh_access_token(
                    account.access_token
                )

                account.access_token = refresh_data["access_token"]
                account.token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=refresh_data["expires_in"]
                )
                account.updated_at = datetime.now(timezone.utc)
                db.commit()

        return account.access_token


# Singleton instance
instagram_oauth_service = InstagramOAuthService()
