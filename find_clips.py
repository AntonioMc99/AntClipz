"""
PHASE 1 - Clip finder.

Finds the most-viewed Twitch clips of one streamer from the last N hours,
prints them, and saves them to data/clips_found.json for the download step.

Run it with:   python find_clips.py
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from antclipz.twitch_api import TwitchClient, TwitchError

OUTPUT_FILE = Path("data") / "clips_found.json"


def to_rfc3339(dt: datetime) -> str:
    """Twitch wants times like 2026-11-23T14:00:00Z (UTC)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    load_dotenv()  # reads the .env file into environment variables

    streamer = os.getenv("STREAMER_LOGIN", "kaicenat").strip()
    lookback_hours = int(os.getenv("LOOKBACK_HOURS", "24"))
    top_n = int(os.getenv("TOP_N", "10"))

    try:
        twitch = TwitchClient(
            os.getenv("TWITCH_CLIENT_ID", "").strip(),
            os.getenv("TWITCH_CLIENT_SECRET", "").strip(),
        )
        print(f"Logged in to Twitch. Looking up '{streamer}'...")
        broadcaster_id = twitch.get_user_id(streamer)

        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=lookback_hours)
        clips = twitch.get_clips(broadcaster_id, to_rfc3339(start), to_rfc3339(now))
    except TwitchError as err:
        print(f"\nERROR: {err}")
        return 1
    except requests.RequestException as err:
        print(f"\nERROR: Could not reach Twitch. Check your internet connection.\nDetails: {err}")
        return 1

    if not clips:
        print(f"\nNo clips of {streamer} in the last {lookback_hours} hours. "
              "They may not have streamed. Try LOOKBACK_HOURS=72 in .env.")
        return 0

    # Most views first, then keep only the top N.
    clips.sort(key=lambda c: c["view_count"], reverse=True)
    top = clips[:top_n]

    # Keep only the fields later phases need (smaller, easier to read file).
    results = [
        {
            "rank": i,
            "id": c["id"],
            "title": c["title"],
            "url": c["url"],
            "views": c["view_count"],
            "duration_seconds": c["duration"],
            "created_at": c["created_at"],
            "streamer": c["broadcaster_name"],
            "streamer_url": f"https://twitch.tv/{streamer}",
            "clipped_by": c["creator_name"],
            "thumbnail_url": c["thumbnail_url"],
        }
        for i, c in enumerate(top, start=1)
    ]

    print(f"\nFound {len(clips)} clips. Top {len(results)} by views:\n")
    for r in results:
        print(f"#{r['rank']:>2}  {r['views']:>8,} views  {r['duration_seconds']:>5.1f}s  {r['title']}")
        print(f"     {r['url']}")

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(
            {"streamer": streamer, "searched_at": to_rfc3339(now),
             "lookback_hours": lookback_hours, "clips": results},
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved to {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
