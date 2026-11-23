"""
Small helper for talking to the Twitch Helix API.

How Twitch login works for us (the "client credentials" flow):
  1. We send our Client ID + Client Secret to Twitch.
  2. Twitch gives back an "app access token" (a temporary password, ~60 days).
  3. We send that token with every API request.
No personal Twitch login is needed because clips are public data.
"""

import requests

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
HELIX_URL = "https://api.twitch.tv/helix"
TIMEOUT_SECONDS = 15


class TwitchError(Exception):
    """Raised when Twitch returns an error we can explain to the user."""


class TwitchClient:
    def __init__(self, client_id: str, client_secret: str):
        if not client_id or not client_secret:
            raise TwitchError(
                "TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET is empty. "
                "Open your .env file and fill them in "
                "(get them from https://dev.twitch.tv/console -> Applications -> Manage)."
            )
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = self._get_app_token()

    def _get_app_token(self) -> str:
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code in (400, 401, 403):
            raise TwitchError(
                "Twitch rejected your Client ID / Client Secret. "
                "Double-check both values in .env (no spaces, no quotes). "
                "If you clicked 'New Secret', the old secret no longer works."
            )
        response.raise_for_status()
        return response.json()["access_token"]

    def _get(self, path: str, params: dict) -> dict:
        response = requests.get(
            f"{HELIX_URL}/{path}",
            headers={
                "Client-Id": self.client_id,
                "Authorization": f"Bearer {self.token}",
            },
            params=params,
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code == 429:
            raise TwitchError("Twitch rate limit hit. Wait a minute and try again.")
        response.raise_for_status()
        return response.json()

    def get_user_id(self, login: str) -> str:
        """Turn a username like 'kaicenat' into Twitch's numeric broadcaster ID."""
        data = self._get("users", {"login": login.lower()})["data"]
        if not data:
            raise TwitchError(f"No Twitch user found with the name '{login}'.")
        return data[0]["id"]

    def get_clips(self, broadcaster_id: str, started_at: str, ended_at: str,
                  max_clips: int = 300) -> list[dict]:
        """
        Get clips created between started_at and ended_at (RFC 3339 times).
        Twitch returns up to 100 per page, so we follow the 'cursor' to get more pages,
        stopping at max_clips so we don't make endless requests.
        """
        clips: list[dict] = []
        cursor = None
        while len(clips) < max_clips:
            params = {
                "broadcaster_id": broadcaster_id,
                "started_at": started_at,
                "ended_at": ended_at,
                "first": 100,
            }
            if cursor:
                params["after"] = cursor
            body = self._get("clips", params)
            clips.extend(body["data"])
            cursor = body.get("pagination", {}).get("cursor")
            if not cursor or not body["data"]:
                break
        return clips
