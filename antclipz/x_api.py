"""
Small helper for posting a video to X (Twitter) with the X API v2.

Login: OAuth 1.0a "user context". You copy 4 keys from the X Developer Console
(API Key + Secret for your app, Access Token + Secret for your X account).
Every request is signed with them, so X knows which account is posting.

Posting a video takes 5 steps:
  1. initialize -> tell X the file size and type, get an upload id
  2. append     -> send the file in 4 MB pieces
  3. finalize   -> tell X the upload is complete
  4. status     -> wait while X processes the video
  5. create post -> post the text with the video attached
Endpoints and fields follow X's official Python SDK (xdk).
"""

import time
from pathlib import Path

import requests
from requests_oauthlib import OAuth1

API = "https://api.x.com"
CHUNK_BYTES = 4 * 1024 * 1024
TIMEOUT = 60
MAX_PROCESSING_WAIT_SECONDS = 300


class XError(Exception):
    """An X API problem we can explain to the user."""


def _explain(response: requests.Response, step: str) -> XError:
    code = response.status_code
    hint = {
        401: "X rejected your keys. Check the 4 X_ values in .env. If you changed the app "
             "permissions to 'Read and write', you must REGENERATE the Access Token and Secret.",
        402: "Your X API account is out of credits. Add credits in the X Developer Console.",
        403: "X refused this action. Usually: the app isn't set to 'Read and write', the account "
             "has no credits, or X flagged the post (e.g. a duplicate of an earlier post).",
        429: "X rate limit hit. Wait 15 minutes and try again.",
    }.get(code, "")
    return XError(f"{step} failed (HTTP {code}). {hint}\nX said: {response.text[:500]}")


class XClient:
    def __init__(self, api_key: str, api_secret: str, access_token: str, access_secret: str,
                 session: requests.Session | None = None):
        missing = [name for name, value in [
            ("X_API_KEY", api_key), ("X_API_SECRET", api_secret),
            ("X_ACCESS_TOKEN", access_token), ("X_ACCESS_TOKEN_SECRET", access_secret),
        ] if not value]
        if missing:
            raise XError(f"Missing in .env: {', '.join(missing)}. See README 'Phase 5' for where to get them.")
        self.session = session or requests.Session()
        self.session.auth = OAuth1(api_key, api_secret, access_token, access_secret)

    def upload_video(self, path: Path, on_progress=print) -> str:
        """Upload an MP4 and return its media id once X has finished processing it."""
        size = path.stat().st_size

        r = self.session.post(f"{API}/2/media/upload/initialize", timeout=TIMEOUT, json={
            "media_type": "video/mp4",
            "media_category": "tweet_video",
            "total_bytes": size,
        })
        if not r.ok:
            raise _explain(r, "Upload (initialize)")
        media_id = r.json()["data"]["id"]

        with path.open("rb") as f:
            index = 0
            while chunk := f.read(CHUNK_BYTES):
                r = self.session.post(
                    f"{API}/2/media/upload/{media_id}/append", timeout=TIMEOUT,
                    data={"segment_index": str(index)},
                    files={"media": ("chunk", chunk, "application/octet-stream")},
                )
                if not r.ok:
                    raise _explain(r, f"Upload (piece {index + 1})")
                index += 1
                sent = min(index * CHUNK_BYTES, size)
                on_progress(f"      uploaded {sent / size:.0%}")

        r = self.session.post(f"{API}/2/media/upload/{media_id}/finalize", timeout=TIMEOUT)
        if not r.ok:
            raise _explain(r, "Upload (finalize)")
        info = r.json()["data"].get("processing_info")

        waited = 0
        while info and info.get("state") not in ("succeeded", None):
            if info.get("state") == "failed":
                raise XError(f"X could not process the video: {info}")
            wait = info.get("check_after_secs", 2)
            if waited > MAX_PROCESSING_WAIT_SECONDS:
                raise XError("X took too long to process the video. Try again later.")
            on_progress(f"      X is processing the video ({info.get('progress_percent', 0)}%)...")
            time.sleep(wait)
            waited += wait
            r = self.session.get(f"{API}/2/media/upload", timeout=TIMEOUT,
                                 params={"command": "STATUS", "media_id": media_id})
            if not r.ok:
                raise _explain(r, "Upload (status check)")
            info = r.json()["data"].get("processing_info")
        return media_id

    def create_post(self, text: str, media_id: str) -> str:
        """Post the text with the video. Returns the new post's id."""
        r = self.session.post(f"{API}/2/tweets", timeout=TIMEOUT, json={
            "text": text,
            "media": {"media_ids": [media_id]},
        })
        if not r.ok:
            raise _explain(r, "Creating the post")
        return r.json()["data"]["id"]
