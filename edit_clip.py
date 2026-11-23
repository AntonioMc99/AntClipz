"""
PHASE 3 - Clip editor.

Takes a downloaded clip and makes a vertical 9:16 (1080x1920) video for
TikTok / Reels / Shorts / X:
  1. Finds the streamer's face and crops around it.
  2. Transcribes the speech with Whisper (free, runs on your PC).
  3. Burns big captions onto the video.
  4. Adds a credit line at the top (e.g. "twitch.tv/kaicenat").

Run it with:
    python edit_clip.py        -> edits the #1 clip
    python edit_clip.py 3      -> edits the #3 clip
(The clip must be downloaded first with download-clip.bat.)
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
from dotenv import load_dotenv

from antclipz.captions import group_words, render_text_png, transcribe_words
from antclipz.face_crop import find_face_center, get_video_info, vertical_crop_box

CLIPS_FILE = Path("data") / "clips_found.json"
DOWNLOAD_DIR = Path("data") / "downloads"
EDITED_DIR = Path("data") / "edited"

OUT_W, OUT_H = 1080, 1920
CAPTION_Y = int(OUT_H * 0.68)      # captions sit in the lower-middle (clear of app buttons)
CREDIT_Y = 140                     # credit line near the top


def pick_clip(rank: int) -> dict:
    found = json.loads(CLIPS_FILE.read_text(encoding="utf-8"))
    clip = next((c for c in found["clips"] if c["rank"] == rank), None)
    if clip is None:
        raise SystemExit(f"ERROR: No clip with rank #{rank} in clips_found.json.")
    return clip


def build_ffmpeg_command(video: Path, output: Path, crop: tuple[int, int, int, int],
                         credit_png: Path, captions: list[dict], max_seconds: float) -> list[str]:
    crop_w, crop_h, x, y = crop
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(video), "-i", str(credit_png)]
    for cap in captions:
        cmd += ["-i", str(cap["png"])]

    # Filter chain: crop -> scale to 1080x1920 -> credit -> each caption at its time.
    parts = [f"[0:v]crop={crop_w}:{crop_h}:{x}:{y},scale={OUT_W}:{OUT_H},setsar=1[v0]",
             f"[v0][1:v]overlay=0:{CREDIT_Y}[v1]"]
    last = "v1"
    for i, cap in enumerate(captions):
        out_label = f"c{i}"
        parts.append(
            f"[{last}][{i + 2}:v]overlay=0:{cap['y']}:"
            f"enable='between(t,{cap['start']:.2f},{cap['end']:.2f})'[{out_label}]"
        )
        last = out_label

    cmd += ["-filter_complex", ";".join(parts),
            "-map", f"[{last}]", "-map", "0:a?",
            "-t", str(max_seconds),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart",
            str(output)]
    return cmd


def main() -> int:
    load_dotenv()
    model_name = os.getenv("WHISPER_MODEL", "base").strip()
    language = os.getenv("WHISPER_LANGUAGE", "en").strip()
    max_seconds = float(os.getenv("MAX_CLIP_SECONDS", "60"))

    if not CLIPS_FILE.exists():
        print("ERROR: data/clips_found.json not found. Run find-clips.bat first.")
        return 1
    if len(sys.argv) > 1 and not sys.argv[1].isdigit():
        print("ERROR: The rank must be a number, like:  edit-clip.bat 3")
        return 1
    rank = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    clip = pick_clip(rank)
    video = DOWNLOAD_DIR / f"{clip['id']}.mp4"
    if not video.exists():
        print(f"ERROR: Clip #{rank} is not downloaded yet. Run:  .\\download-clip.bat {rank}")
        return 1

    EDITED_DIR.mkdir(parents=True, exist_ok=True)
    work_dir = EDITED_DIR / f"_work_{clip['id']}"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir()
    output = EDITED_DIR / f"{clip['id']}.mp4"
    started = time.time()

    print(f"Editing clip #{rank}: {clip['title']}")

    # 1. Face + crop
    info = get_video_info(str(video))
    print(f"[1/4] Finding the face in {info['width']}x{info['height']} video...")
    face = find_face_center(str(video))
    crop = vertical_crop_box(info["width"], info["height"], face)
    print("      Face found, centering on it." if face else "      No face found, using the center of the screen.")

    # 2. Transcribe
    print(f"[2/4] Transcribing speech with Whisper ('{model_name}' model)...")
    print("      (The first time, this downloads the model, about 150 MB. Later runs are faster.)")
    words = transcribe_words(str(video), model_name, language or None)
    captions = [c for c in group_words(words) if c["start"] < max_seconds]
    transcript = " ".join(w["text"] for w in words)
    print(f"      Heard: {transcript[:120] + ('...' if len(transcript) > 120 else '') or '(no speech)'}")

    # 3. Draw captions + credit as images
    print(f"[3/4] Drawing {len(captions)} captions...")
    for i, cap in enumerate(captions):
        cap["png"] = work_dir / f"cap_{i:03d}.png"
        _, h = render_text_png(cap["text"], cap["png"], OUT_W, font_size=86, stroke=7, max_text_width=940)
        cap["y"] = CAPTION_Y - h // 2
    credit_text = clip["streamer_url"].replace("https://", "")
    credit_png = work_dir / "credit.png"
    render_text_png(credit_text, credit_png, OUT_W, font_size=46, stroke=4, max_text_width=1000)

    # 4. Render with ffmpeg
    print("[4/4] Rendering the vertical video with ffmpeg...")
    cmd = build_ffmpeg_command(video, output, crop, credit_png, captions, max_seconds)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("\nERROR: ffmpeg failed:\n" + result.stderr[-2000:])
        return 1

    # Save an info card for the review step (Phase 4).
    card = dict(clip)
    card.update({
        "edited_file": output.name,
        "transcript": transcript,
        "captions": [{k: c[k] for k in ("text", "start", "end")} for c in captions],
        "face_found": face is not None,
    })
    (EDITED_DIR / f"{clip['id']}.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(work_dir, ignore_errors=True)

    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"\nDone in {time.time() - started:.0f}s. Saved: {output}  ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
