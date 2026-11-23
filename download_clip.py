"""
PHASE 2 - Clip downloader.

Reads data/clips_found.json (made by find_clips.py) and downloads ONE clip
with yt-dlp into data/downloads/. Saves a small .json "info card" next to the
video with the title and streamer, so later phases can credit the creator.

Run it with:
    python download_clip.py        -> downloads the #1 clip
    python download_clip.py 3      -> downloads the #3 clip
"""

import json
import sys
from pathlib import Path

import yt_dlp

CLIPS_FILE = Path("data") / "clips_found.json"
DOWNLOAD_DIR = Path("data") / "downloads"


def main() -> int:
    if not CLIPS_FILE.exists():
        print("ERROR: data/clips_found.json not found. Run find-clips.bat first.")
        return 1

    rank = 1
    if len(sys.argv) > 1:
        if not sys.argv[1].isdigit():
            print("ERROR: The rank must be a number, like:  download-clip.bat 3")
            return 1
        rank = int(sys.argv[1])

    found = json.loads(CLIPS_FILE.read_text(encoding="utf-8"))
    clip = next((c for c in found["clips"] if c["rank"] == rank), None)
    if clip is None:
        print(f"ERROR: No clip with rank #{rank}. clips_found.json has ranks 1-{len(found['clips'])}.")
        return 1

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    video_path = DOWNLOAD_DIR / f"{clip['id']}.mp4"
    info_path = DOWNLOAD_DIR / f"{clip['id']}.json"

    print(f"Clip #{rank}: {clip['title']}")
    print(f"  {clip['views']:,} views, {clip['duration_seconds']}s, by {clip['streamer']}")
    print(f"  {clip['url']}\n")

    if video_path.exists():
        print(f"Already downloaded: {video_path}")
    else:
        options = {
            # Twitch clips come as a single MP4 file, so no merging (or ffmpeg) needed yet.
            "format": "best[ext=mp4]/best",
            "outtmpl": str(video_path),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": False,
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([clip["url"]])
        except yt_dlp.utils.DownloadError as err:
            print(f"\nERROR: Download failed: {err}")
            print("If this keeps happening, update yt-dlp:  .venv\\Scripts\\python -m pip install -U yt-dlp")
            return 1

    # Info card used later for captions + crediting the original streamer.
    info_path.write_text(json.dumps(clip, indent=2, ensure_ascii=False), encoding="utf-8")

    size_mb = video_path.stat().st_size / (1024 * 1024)
    print(f"\nSaved video: {video_path}  ({size_mb:.1f} MB)")
    print(f"Saved info:  {info_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
