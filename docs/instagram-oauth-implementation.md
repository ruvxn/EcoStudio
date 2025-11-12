# Instagram OAuth and Data Sync Implementation

## Overview

This document describes the implementation of Instagram OAuth authentication and historical data synchronization for EcoTrainer Studio Phase 1.

## Architecture

```
┌──────────────┐
│   Frontend   │
│              │
└──────┬───────┘
       │
       │ 1. POST /api/v1/accounts/connect
       ↓
┌──────────────────────────────────────────────────────────────┐
│                    Backend API                                │
│                                                               │
│  ┌────────────────────────────────────────────────────┐     │
│  │          accounts.py (API Endpoints)                │     │
│  │  - connect_account()                                │     │
│  │  - instagram_oauth_callback()                       │     │
│  │  - sync_account_data()                              │     │
│  │  - get_account_stats()                              │     │
│  └────────┬───────────────────────────┬─────────────────┘     │
│           │                           │                       │
│           ↓                           ↓                       │
│  ┌──────────────────┐      ┌──────────────────┐             │
│  │  instagram_      │      │  instagram_      │             │
│  │  oauth.py        │      │  sync.py         │             │
│  │  (OAuth Flow)    │      │  (Data Sync)     │             │
│  └────────┬─────────┘      └────────┬─────────┘             │
│           │                         │                        │
└───────────┼─────────────────────────┼────────────────────────┘
            │                         │
            ↓                         ↓
   ┌────────────────────┐    ┌────────────────────┐
   │  Instagram Graph   │    │  Instagram Graph   │
   │  OAuth API         │    │  Media API         │
   └────────────────────┘    └────────────────────┘
```

## Components

### 1. Instagram OAuth Service (`instagram_oauth.py`)

**Purpose**: Manages the complete OAuth 2.0 flow for Instagram authentication.

#### Key Methods

##### `get_authorization_url(state: Optional[str]) -> str`
Generates the Instagram authorization URL to redirect users to.

**Parameters:**
- `state`: Optional CSRF protection token (recommended for production)

**Returns:** Authorization URL

**Example:**
```python
auth_url = instagram_oauth_service.get_authorization_url(state="random_token")
# Returns: https://api.instagram.com/oauth/authorize?client_id=...&scope=user_profile,user_media
```

##### `exchange_code_for_token(code: str) -> Dict`
Exchanges the authorization code for access tokens.

**Flow:**
1. Exchange code for short-lived token (1 hour)
2. Immediately exchange short-lived for long-lived token (60 days)
3. Return long-lived token data

**Parameters:**
- `code`: Authorization code from Instagram callback

**Returns:**
```python
{
    "access_token": "IGQVj...",
    "token_type": "bearer",
    "expires_in": 5184000  # 60 days in seconds
}
```

##### `refresh_access_token(current_token: str) -> Dict`
Refreshes a long-lived access token before expiration.

**Requirements:**
- Token must be at least 24 hours old
- Token must not be expired

**Parameters:**
- `current_token`: Existing long-lived access token

**Returns:** New token data with extended expiration

##### `get_user_profile(access_token: str) -> Dict`
Fetches user profile information from Instagram.

**Returns:**
```python
{
    "id": "123456789",
    "username": "johndoe",
    "account_type": "PERSONAL",  # or BUSINESS, CREATOR
    "media_count": 150
}
```

##### `save_account(db, access_token, user_id, expires_in, username) -> SocialAccount`
Saves or updates Instagram account credentials in the database.

**Logic:**
- If account exists (by `user_id`): Update token and expiration
- If account is new: Create new `SocialAccount` record

##### `ensure_valid_token(db, account) -> str`
Ensures the account has a valid access token, automatically refreshing if needed.

**Logic:**
- Check token expiration date
- If expiring within 7 days: Automatically refresh
- Update database with new token
- Return valid access token

**Usage:**
```python
# Always call this before making Instagram API requests
token = await instagram_oauth_service.ensure_valid_token(db, account)
```

---

### 2. Instagram Sync Service (`instagram_sync.py`)

**Purpose**: Fetches historical posts from Instagram and stores them in the database for ML training.

#### Key Methods

##### `sync_posts(db, account, days, force_refresh) -> Dict`
Main method to synchronize posts from Instagram.

**Parameters:**
- `db`: Database session
- `account`: SocialAccount instance
- `days`: Number of days to sync (1-365)
- `force_refresh`: If True, bypass the 6-hour sync cooldown

**Protection:** Won't re-sync if last sync was within 6 hours (unless `force_refresh=True`)

**Returns:**
```python
{
    "posts_fetched": 145,
    "posts_new": 120,
    "posts_updated": 25,
    "oldest_post": datetime(2024, 8, 15, 10, 30),
    "newest_post": datetime(2024, 11, 12, 18, 0)
}
```

**Process:**
1. Ensure valid access token
2. Fetch all media from Instagram (with pagination)
3. Filter by date range
4. For each post:
   - Check if exists in database
   - Create new or update existing
   - Calculate engagement score
5. Update `last_sync_at` timestamp

##### `_fetch_all_media(access_token, cutoff_date) -> List[Dict]`
Fetches all media items with pagination support.

**API Fields Fetched:**
- `id`: Post ID
- `caption`: Post text
- `media_type`: IMAGE, VIDEO, or CAROUSEL_ALBUM
- `media_url`: URL to media file
- `thumbnail_url`: For videos
- `permalink`: Public URL to post
- `timestamp`: When posted (ISO 8601)
- `like_count`: Number of likes
- `comments_count`: Number of comments
- `username`: Account username

**Pagination:**
- Instagram returns max 100 items per request
- Follows `paging.next` links until all posts fetched
- Stops when reaching `cutoff_date`

**Rate Limiting:**
- 1 second delay between paginated requests
- Respects Instagram's 200 calls/hour limit

##### `_create_post_from_data(post_data, account_id, follower_count) -> Post`
Creates a Post object from Instagram API response.

**Content Analysis:**
- **Hashtag Count**: Regex pattern `#\w+` to count hashtags
- **Has Emoji**: Unicode ranges for emoji detection
- **Caption Length**: Character count of caption text
- **Content Type**: Maps Instagram types to our enum:
  - `IMAGE` → `ContentType.IMAGE`
  - `VIDEO` → `ContentType.VIDEO`
  - `CAROUSEL_ALBUM` → `ContentType.CAROUSEL`

**Engagement Score Calculation:**
```python
weighted_engagement = (likes + comments * 2 + shares * 3)
engagement_score = weighted_engagement / follower_count
```

**Rationale:**
- Likes = 1x (easy to give)
- Comments = 2x (requires more effort)
- Shares = 3x (highest endorsement)
- Normalize by followers (makes accounts comparable)

##### `_update_post_from_data(post, post_data, follower_count)`
Updates existing post with fresh engagement data.

**Updates:**
- `likes`: Current like count
- `comments`: Current comment count
- `engagement_score`: Recalculated
- `updated_at`: Current timestamp

**Why update?** Engagement metrics can change after initial sync.

---

### 3. API Endpoints (`accounts.py`)

#### Endpoint: `POST /api/v1/accounts/connect`

**Purpose**: Initiate OAuth flow

**Request Body:**
```json
{
  "platform": "instagram"
}
```

**Response:**
```json
{
  "authorization_url": "https://api.instagram.com/oauth/authorize?...",
  "message": "Redirect user to this URL to begin OAuth flow"
}
```

**Frontend Action:** Redirect user to `authorization_url`

---

#### Endpoint: `GET /api/v1/accounts/auth/instagram/callback`

**Purpose**: Handle OAuth callback from Instagram

**Query Parameters:**
- `code`: Authorization code (provided by Instagram)

**Process:**
1. Exchange code for access token
2. Fetch user profile
3. Save account to database
4. Return success with account ID

**Response:**
```json
{
  "success": true,
  "message": "Successfully connected Instagram account @johndoe",
  "account_id": 1,
  "redirect_to": "http://localhost:3000/dashboard?connected=true"
}
```

**Frontend Action:** Redirect to `redirect_to` URL

---

#### Endpoint: `POST /api/v1/accounts/{account_id}/sync`

**Purpose**: Sync historical posts

**Request Body:**
```json
{
  "days": 90,
  "force_refresh": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully synced 145 posts",
  "posts_fetched": 145,
  "posts_new": 120,
  "posts_updated": 25,
  "oldest_post": "2024-08-15T10:30:00Z",
  "newest_post": "2024-11-12T18:00:00Z"
}
```

**Error Handling:**
- 404: Account not found
- 400: Sync failed or too recent (< 6 hours ago)

---

#### Endpoint: `GET /api/v1/accounts/{account_id}/stats`

**Purpose**: Get engagement analytics

**Response:**
```json
{
  "total_posts": 145,
  "avg_engagement": 0.0342,
  "best_posting_hour": 19,
  "best_posting_day": 2,
  "total_likes": 12450,
  "total_comments": 823,
  "total_shares": 0,
  "date_range_start": "2024-08-15T10:30:00Z",
  "date_range_end": "2024-11-12T18:00:00Z"
}
```

**Calculations:**
- **best_posting_hour**: Hour (0-23) with highest average engagement
- **best_posting_day**: Day of week (0-6, Monday-Sunday) with highest average engagement
- **avg_engagement**: Mean of all post engagement scores

**Requirements:** Account must have synced posts (run sync endpoint first)

---

## OAuth Flow Sequence

```
┌─────────┐                ┌─────────┐                ┌──────────────┐
│ Frontend│                │ Backend │                │  Instagram   │
└────┬────┘                └────┬────┘                └──────┬───────┘
     │                          │                            │
     │ 1. User clicks           │                            │
     │    "Connect Instagram"   │                            │
     ├─────────────────────────>│                            │
     │                          │                            │
     │ 2. Return auth URL       │                            │
     │<─────────────────────────┤                            │
     │                          │                            │
     │ 3. Redirect to Instagram │                            │
     ├────────────────────────────────────────────────────────>
     │                          │                            │
     │                          │  4. User approves          │
     │                          │     permissions            │
     │                          │                            │
     │ 5. Redirect to callback  │                            │
     │    with code             │                            │
     │<────────────────────────────────────────────────────────┤
     │                          │                            │
     │ 6. GET /callback?code=X  │                            │
     ├─────────────────────────>│                            │
     │                          │                            │
     │                          │ 7. Exchange code for token │
     │                          ├───────────────────────────>│
     │                          │                            │
     │                          │ 8. Return access token     │
     │                          │<───────────────────────────┤
     │                          │                            │
     │                          │ 9. Get user profile        │
     │                          ├───────────────────────────>│
     │                          │                            │
     │                          │ 10. Return profile         │
     │                          │<───────────────────────────┤
     │                          │                            │
     │                          │ 11. Save to database       │
     │                          │                            │
     │ 12. Return success       │                            │
     │<─────────────────────────┤                            │
     │                          │                            │
     │ 13. Redirect to dashboard│                            │
     │                          │                            │
```

## Data Sync Flow

```
┌─────────┐                ┌─────────┐                ┌──────────────┐
│ Frontend│                │ Backend │                │  Instagram   │
└────┬────┘                └────┬────┘                └──────┬───────┘
     │                          │                            │
     │ 1. POST /sync            │                            │
     │    {days: 90}            │                            │
     ├─────────────────────────>│                            │
     │                          │                            │
     │                          │ 2. Check last_sync_at      │
     │                          │    (< 6 hours ago?)        │
     │                          │                            │
     │                          │ 3. Ensure valid token      │
     │                          │    (refresh if needed)     │
     │                          │                            │
     │                          │ 4. GET /me/media (page 1)  │
     │                          ├────────��──────────────────>│
     │                          │                            │
     │                          │ 5. Return posts + next URL │
     │                          │<───────────────────────────┤
     │                          │                            │
     │                          │ 6. GET next page           │
     │                          ├───────────────────────────>│
     │                          │                            │
     │                          │ 7. Return posts            │
     │                          │<───────────────────────────┤
     │                          │                            │
     │                          │    ... (repeat pagination) │
     │                          │                            │
     │                          │ 8. Process each post:      │
     │                          │    - Parse metrics         │
     │                          │    - Count hashtags        │
     │                          │    - Detect emojis         │
     │                          │    - Calculate engagement  │
     │                          │    - Save to database      │
     │                          │                            │
     │ 9. Return sync results   │                            │
     │<─────────────────────────┤                            │
     │                          │                            │
```

## Database Schema (Relevant Tables)

### social_accounts
```sql
CREATE TABLE social_accounts (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL,
    account_id VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255),
    access_token TEXT NOT NULL,
    token_expires_at TIMESTAMP,
    refresh_token TEXT,
    follower_count INTEGER,
    last_sync_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### posts
```sql
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES social_accounts(id),
    post_id VARCHAR(255) UNIQUE NOT NULL,
    content TEXT,
    post_time TIMESTAMP NOT NULL,

    -- Engagement metrics
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    engagement_score FLOAT,

    -- Content features (for ML)
    content_type VARCHAR(50) NOT NULL,
    caption_length INTEGER,
    hashtag_count INTEGER,
    has_emoji INTEGER,
    media_url TEXT,

    synced_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Configuration

### Environment Variables

```bash
# Instagram OAuth
INSTAGRAM_CLIENT_ID=your_client_id
INSTAGRAM_CLIENT_SECRET=your_client_secret
INSTAGRAM_REDIRECT_URI=http://localhost:8000/api/v1/accounts/auth/instagram/callback

# Frontend
FRONTEND_URL=http://localhost:3000
```

### Instagram App Setup

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Create a new app
3. Add "Instagram Basic Display" product
4. Configure OAuth redirect URIs
5. Add required scopes: `user_profile`, `user_media`
6. Get Client ID and Client Secret

## Error Handling

### InstagramOAuthError
Raised when OAuth operations fail.

**Common Causes:**
- Invalid authorization code
- Expired authorization code
- Invalid client credentials
- Network errors

**Example:**
```python
try:
    token_data = await instagram_oauth_service.exchange_code_for_token(code)
except InstagramOAuthError as e:
    # Handle OAuth failure
    return {"error": str(e)}
```

### InstagramSyncError
Raised when data sync fails.

**Common Causes:**
- Expired access token
- Rate limit exceeded
- Network timeout
- Invalid permissions

**Example:**
```python
try:
    result = await instagram_sync_service.sync_posts(db, account, days=90)
except InstagramSyncError as e:
    # Handle sync failure
    return {"error": str(e)}
```

## Rate Limiting

### Instagram API Limits
- **200 calls per hour** per user token
- **25 posts per page** (default)
- **100 posts per page** (maximum)

### Our Implementation
- 1 second delay between paginated requests
- Track sync timestamps (prevent spam)
- Cooldown: 6 hours between syncs (override with `force_refresh`)

## Security Considerations

### Token Storage
**Current Implementation:** Tokens stored as plain text in database

**Production Recommendations:**
1. Encrypt access tokens using Fernet or similar
2. Use environment variable for encryption key
3. Store encryption key in AWS Secrets Manager

**Example:**
```python
from cryptography.fernet import Fernet

class TokenEncryption:
    def __init__(self, key: bytes):
        self.cipher = Fernet(key)

    def encrypt(self, token: str) -> bytes:
        return self.cipher.encrypt(token.encode())

    def decrypt(self, encrypted: bytes) -> str:
        return self.cipher.decrypt(encrypted).decode()
```

### CSRF Protection
The `state` parameter in OAuth flow protects against CSRF attacks.

**Recommendation for Production:**
```python
import secrets

# Generate random state
state = secrets.token_urlsafe(32)

# Store in session
session["oauth_state"] = state

# Include in authorization URL
auth_url = oauth_service.get_authorization_url(state=state)

# Verify in callback
if request.args.get("state") != session.get("oauth_state"):
    raise SecurityError("Invalid state parameter")
```

## Testing

### Manual Testing Flow

1. **Test OAuth Connection:**
```bash
curl -X POST http://localhost:8000/api/v1/accounts/connect \
  -H "Content-Type: application/json" \
  -d '{"platform": "instagram"}'
```

2. **Visit authorization URL** (from response)

3. **After callback, test sync:**
```bash
curl -X POST http://localhost:8000/api/v1/accounts/1/sync \
  -H "Content-Type: application/json" \
  -d '{"days": 90, "force_refresh": false}'
```

4. **View statistics:**
```bash
curl http://localhost:8000/api/v1/accounts/1/stats
```

### Unit Testing (Future)

```python
# tests/test_instagram_oauth.py
import pytest
from app.services.instagram_oauth import instagram_oauth_service

def test_authorization_url():
    url = instagram_oauth_service.get_authorization_url()
    assert "api.instagram.com/oauth/authorize" in url
    assert f"client_id={settings.INSTAGRAM_CLIENT_ID}" in url
    assert "scope=user_profile,user_media" in url

@pytest.mark.asyncio
async def test_token_exchange(mock_httpx):
    # Mock Instagram API response
    mock_httpx.post.return_value.json.return_value = {
        "access_token": "test_token",
        "user_id": "12345"
    }

    result = await instagram_oauth_service.exchange_code_for_token("test_code")
    assert result["access_token"] == "test_token"
```

## Future Enhancements

### Phase 2 Additions

1. **Business Account Support:**
   - Fetch follower count from API
   - Access Instagram Insights for better metrics
   - Story and Reel analytics

2. **Background Job Queue:**
   - Move sync to async job queue (Celery/APScheduler)
   - Schedule periodic syncs
   - Handle long-running syncs better

3. **Webhook Integration:**
   - Real-time updates when posts are created
   - Automatic engagement metric updates
   - No need to manually sync

4. **Multi-Account Support:**
   - User authentication system
   - Associate multiple Instagram accounts per user
   - Account switching in dashboard

## Troubleshooting

### "OAuth failed: Failed to exchange code for token"

**Cause:** Authorization code is invalid or expired

**Solution:**
- Authorization codes expire quickly (minutes)
- Don't refresh page during OAuth flow
- Ensure redirect URI matches Instagram app settings exactly

### "Sync failed: Account synced X hours ago"

**Cause:** Attempting to sync too frequently

**Solution:**
- Wait 6 hours between syncs
- Use `force_refresh: true` if necessary
- Check `last_sync_at` timestamp in database

### "No posts found for this account"

**Cause:** Posts haven't been synced yet

**Solution:**
- Run `POST /api/v1/accounts/{id}/sync` first
- Check that account has posts on Instagram
- Verify date range (default: 90 days)

## Conclusion

The Instagram OAuth and data sync implementation provides a robust foundation for:
- Secure user authentication
- Historical data collection
- Engagement analytics
- ML model training data

This completes Phase 1 requirement: **Instagram API integration (OAuth + data sync)** ✅

**Next:** Build the ML engagement prediction model using this synced data.
