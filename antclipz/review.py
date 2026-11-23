"""
Review folders (Phase 4) - shared by send_to_review.py and the poster (Phase 5).

The review folder lives inside Google Drive (synced by the "Google Drive for
desktop" app), so you can watch clips on your phone in the Drive app:

    antclipz/
      1 - to review/     <- new clips land here
      2 - approved/      <- YOU move clips here from your phone to approve them
      3 - rejected/      <- or here to reject them
      4 - posted/        <- the poster moves clips here after posting
      captions/          <- one .txt per clip: the text that will be posted with it

Only clips in "2 - approved" will ever be posted.
"""

import os
import re
import string
from pathlib import Path

TO_REVIEW = "1 - to review"
APPROVED = "2 - approved"
REJECTED = "3 - rejected"
POSTED = "4 - posted"
CAPTIONS = "captions"
ALL_FOLDERS = [TO_REVIEW, APPROVED, REJECTED, POSTED, CAPTIONS]


def find_google_drive() -> Path | None:
    """Google Drive for desktop shows up as a drive letter (usually G:) with a 'My Drive' folder."""
    for letter in string.ascii_uppercase[3:]:   # D: to Z:
        my_drive = Path(f"{letter}:\\My Drive")
        if my_drive.is_dir():
            return my_drive
    return None


def get_review_root() -> tuple[Path, bool]:
    """
    Returns (review folder, is_in_google_drive).
    Uses REVIEW_DIR from .env if set, otherwise <Google Drive>\\My Drive\\antclipz,
    otherwise falls back to data\\review on this PC.
    """
    custom = os.getenv("REVIEW_DIR", "").strip().strip('"')
    if custom:
        root = Path(custom)
        return root, "My Drive" in root.parts
    drive = find_google_drive()
    if drive:
        return drive / "antclipz", True
    return Path("data") / "review", False


def make_folders(root: Path) -> None:
    for name in ALL_FOLDERS:
        (root / name).mkdir(parents=True, exist_ok=True)


def safe_filename(text: str, max_len: int = 60) -> str:
    """Make a clip title safe to use in a Windows filename."""
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f#]', "", text)   # characters Windows doesn't allow
    text = re.sub(r"\s+", " ", text).strip(" .")
    return (text[:max_len].strip(" .") or "clip")


def clip_id_from_filename(name: str) -> str:
    """Filenames end with ' [<clip id>].mp4' so we can always find the clip again."""
    match = re.search(r"\[([^\[\]]+)\]\.mp4$", name)
    return match.group(1) if match else ""


def find_clip_everywhere(root: Path, clip_id: str) -> list[Path]:
    """Every copy of this clip in any review folder (so we don't send it twice)."""
    hits = []
    for name in (TO_REVIEW, APPROVED, REJECTED, POSTED):
        folder = root / name
        if folder.is_dir():
            hits += [p for p in folder.glob("*.mp4") if clip_id_from_filename(p.name) == clip_id]
    return hits
