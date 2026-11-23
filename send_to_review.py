"""
PHASE 4 - Send a finished clip to your review folder (Google Drive).

Copies the edited video into "1 - to review" and writes a draft post caption
into "captions". Then you approve or reject it from your phone by moving the
video in the Google Drive app.

Run it with:
    python send_to_review.py        -> sends the #1 clip
    python send_to_review.py 3      -> sends the #3 clip
(The clip must be edited first with edit-clip.bat.)
"""

import json
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

from antclipz.review import (APPROVED, CAPTIONS, TO_REVIEW, find_clip_everywhere,
                             get_review_root, make_folders, safe_filename)

CLIPS_FILE = Path("data") / "clips_found.json"
EDITED_DIR = Path("data") / "edited"


def draft_caption(card: dict) -> str:
    """The text that will be posted with the clip. Always credits the streamer."""
    streamer = card["streamer"]
    title = card["title"].strip()
    tag = "#" + "".join(ch for ch in streamer if ch.isalnum())
    return (
        f"{title}\n"
        f"\n"
        f"🎥 Credit: {streamer} on Twitch - {card['streamer_url'].replace('https://', '')}\n"
        f"{tag} #twitch #clips"
    )


def main() -> int:
    load_dotenv()
    if not CLIPS_FILE.exists():
        print("ERROR: data/clips_found.json not found. Run find-clips.bat first.")
        return 1
    if len(sys.argv) > 1 and not sys.argv[1].isdigit():
        print("ERROR: The rank must be a number, like:  send-to-review.bat 3")
        return 1
    rank = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    found = json.loads(CLIPS_FILE.read_text(encoding="utf-8"))
    clip = next((c for c in found["clips"] if c["rank"] == rank), None)
    if clip is None:
        print(f"ERROR: No clip with rank #{rank} in clips_found.json.")
        return 1

    video = EDITED_DIR / f"{clip['id']}.mp4"
    card_file = EDITED_DIR / f"{clip['id']}.json"
    if not video.exists() or not card_file.exists():
        print(f"ERROR: Clip #{rank} isn't edited yet. Run:  .\\edit-clip.bat {rank}")
        return 1
    card = json.loads(card_file.read_text(encoding="utf-8"))

    root, in_drive = get_review_root()
    make_folders(root)

    already = find_clip_everywhere(root, clip["id"])
    if already:
        where = already[0].parent.name
        print(f"This clip is already in your review folder ('{where}'). Not sending it again.")
        print(f"  {already[0]}")
        return 0

    base = f"{safe_filename(card['streamer'])} - {safe_filename(card['title'])} [{clip['id']}]"
    target_video = root / TO_REVIEW / f"{base}.mp4"
    caption_file = root / CAPTIONS / f"{base}.txt"

    shutil.copy2(video, target_video)
    caption_file.write_text(draft_caption(card), encoding="utf-8")

    print(f"Sent clip #{rank} to review: {card['title']}")
    print(f"  Video:   {target_video}")
    print(f"  Caption: {caption_file}")
    print()
    print("Draft post caption:")
    print("-" * 40)
    print(draft_caption(card))
    print("-" * 40)
    print()
    if in_drive:
        print("On your phone: open the Google Drive app -> antclipz -> '1 - to review'.")
        print(f"Watch it, then move it to '{APPROVED}' to approve (or '3 - rejected').")
        print("(Google Drive can take a few minutes to upload and process a new video.)")
    else:
        print("NOTE: Google Drive for desktop was not found, so the clip was saved on this PC only")
        print(f"      in {root}. Install Google Drive for desktop to review on your phone (see README).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
