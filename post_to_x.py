"""
PHASE 5a - Post APPROVED clips to X.

Only looks at the "2 - approved" folder in your review folder (Google Drive).
For each approved clip (one per run by default):
  1. Reads its caption from the "captions" folder.
  2. Safety checks: caption exists, isn't too long, has no link (links cost much more on X).
  3. Shows you the caption and asks you to type YES before anything is posted.
  4. Uploads the video, posts it, moves the video to "4 - posted", logs it.

Run it with:   python post_to_x.py
"""

import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from antclipz.review import APPROVED, CAPTIONS, POSTED, clip_id_from_filename, get_review_root
from antclipz.x_api import XClient, XError

POST_LOG = Path("data") / "posted_log.json"
MAX_POST_CHARS = 280
# Looks for anything X would turn into a link: http..., www..., or name.tld (twitch.tv, kick.com, ...)
LINK_PATTERN = re.compile(r"(https?://|www\.|\b[\w-]+\.(com|tv|net|org|gg|io|ly|co|me|app|live)\b)", re.I)


def x_length(text: str) -> int:
    """X counts emoji and many symbols as 2 characters. This is a close, slightly safe estimate."""
    return sum(2 if ord(ch) > 0x2FFF else 1 for ch in text)


def load_log() -> list[dict]:
    if POST_LOG.exists():
        return json.loads(POST_LOG.read_text(encoding="utf-8"))
    return []


def main() -> int:
    load_dotenv()
    max_posts = int(os.getenv("MAX_POSTS_PER_RUN", "1"))
    allow_links = os.getenv("ALLOW_LINKS_IN_POSTS", "false").strip().lower() == "true"

    root, _ = get_review_root()
    approved_dir = root / APPROVED
    if not approved_dir.is_dir():
        print(f"ERROR: Review folder not found: {approved_dir}\nRun send-to-review.bat first.")
        return 1

    approved = sorted(approved_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not approved:
        print(f"No approved clips. On your phone, move a clip into '{APPROVED}' first.")
        return 0
    print(f"{len(approved)} approved clip(s). Posting up to {max_posts} this run.\n")

    try:
        x = XClient(os.getenv("X_API_KEY", "").strip(), os.getenv("X_API_SECRET", "").strip(),
                    os.getenv("X_ACCESS_TOKEN", "").strip(), os.getenv("X_ACCESS_TOKEN_SECRET", "").strip())
    except XError as err:
        print(f"ERROR: {err}")
        return 1

    log = load_log()
    already_posted = {entry["clip_id"] for entry in log}
    posted_count = 0

    for video in approved:
        if posted_count >= max_posts:
            break
        clip_id = clip_id_from_filename(video.name)
        print(f"=== {video.name}")

        if clip_id in already_posted:
            print("    Already posted before (see data/posted_log.json). Moving it to '4 - posted'.\n")
            shutil.move(str(video), str(root / POSTED / video.name))
            continue

        caption_file = root / CAPTIONS / (video.stem + ".txt")
        if not caption_file.exists():
            print(f"    SKIPPED: no caption file at {caption_file}\n")
            continue
        caption = caption_file.read_text(encoding="utf-8").strip()

        if not caption:
            print("    SKIPPED: the caption file is empty.\n")
            continue
        if x_length(caption) > MAX_POST_CHARS:
            print(f"    SKIPPED: caption is about {x_length(caption)} characters (X max is {MAX_POST_CHARS}). "
                  f"Shorten it in:\n    {caption_file}\n")
            continue
        link = LINK_PATTERN.search(caption)
        if link and not allow_links:
            print(f"    SKIPPED: the caption contains a link ('{link.group(0)}').")
            print("    X charges a lot more for posts with links. Remove it from:")
            print(f"    {caption_file}\n")
            continue

        print("    Caption:")
        print("    " + "-" * 40)
        for line in caption.splitlines():
            print(f"    {line}")
        print("    " + "-" * 40)
        answer = input("    Type YES to post this to X (anything else skips): ").strip()
        if answer != "YES":
            print("    Skipped. It stays in '2 - approved'.\n")
            continue

        try:
            print("    Uploading video to X...")
            media_id = x.upload_video(video, on_progress=print)
            print("    Posting...")
            post_id = x.create_post(caption, media_id)
        except XError as err:
            print(f"\nERROR: {err}")
            return 1
        except requests.RequestException as err:
            print(f"\nERROR: Could not reach X. Check your internet connection.\nDetails: {err}")
            return 1

        url = f"https://x.com/i/status/{post_id}"
        shutil.move(str(video), str(root / POSTED / video.name))
        log.append({"clip_id": clip_id, "file": video.name, "x_post_id": post_id, "x_url": url,
                    "caption": caption, "posted_at": datetime.now(timezone.utc).isoformat()})
        POST_LOG.parent.mkdir(exist_ok=True)
        POST_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
        posted_count += 1
        print(f"    POSTED: {url}")
        print("    Moved the video to '4 - posted'.\n")

    print(f"Done. Posted {posted_count} clip(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
