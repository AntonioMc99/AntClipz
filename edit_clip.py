"""
PHASE 3 - Clip editor.

Takes a downloaded clip and makes a vertical 9:16 (1080x1920) video for
TikTok / Reels / Shorts / X:
  1. Finds the streamer's face and picks a layout:
       - "split": facecam on top, gameplay below (for game streams with a small facecam)
       - "crop":  one tall slice centered on the face (for IRL / full-camera streams)
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
from antclipz.face_crop import find_face, get_video_info, split_layout_boxes, vertical_crop_box

CLIPS_FILE = Path("data") / "clips_found.json"
DOWNLOAD_DIR = Path("data") / "downloads"
EDITED_DIR = Path("data") / "edited"

OUT_W, OUT_H = 1080, 1920
TOP_H = 608                        # split layout: facecam panel height (16:9 at 1080 wide)
BOTTOM_H = OUT_H - TOP_H           # split layout: gameplay panel height
SMALL_FACE_RATIO = 0.08            # face narrower than 8% of the frame = small facecam -> split


def pick_clip(rank: int) -> dict:
    found = json.loads(CLIPS_FILE.read_text(encoding="utf-8"))
    clip = next((c for c in found["clips"] if c["rank"] == rank), None)
    if clip is None:
        raise SystemExit(f"ERROR: No clip with rank #{rank} in clips_found.json.")
    return clip


def choose_layout(setting: str, face: dict, width: int) -> str:
    if setting in ("split", "crop"):
        return setting if (setting == "crop" or face["center"]) else "crop"
    # auto
    if face["center"] and face["size"][0] / width < SMALL_FACE_RATIO:
        return "split"
    return "crop"


def base_video_filter(layout: str, info: dict, face: dict) -> str:
    """The ffmpeg filter that builds the 1080x1920 picture, ending in label [v0]."""
    w, h = info["width"], info["height"]
    if layout == "split":
        (cw, ch, cx, cy), (gw, gh, gx, gy) = split_layout_boxes(
            w, h, face["center"], face["size"], OUT_W / TOP_H, OUT_W / BOTTOM_H)
        return (f"[0:v]split=2[cam][game];"
                f"[cam]crop={cw}:{ch}:{cx}:{cy},scale={OUT_W}:{TOP_H},setsar=1[top];"
                f"[game]crop={gw}:{gh}:{gx}:{gy},scale={OUT_W}:{BOTTOM_H},setsar=1[bottom];"
                f"[top][bottom]vstack=inputs=2[v0]")
    cw, ch, cx, cy = vertical_crop_box(w, h, face["center"])
    return f"[0:v]crop={cw}:{ch}:{cx}:{cy},scale={OUT_W}:{OUT_H},setsar=1[v0]"


def build_ffmpeg_command(video: Path, output: Path, base_filter: str, credit_png: Path,
                         credit_y: int, captions: list[dict], max_seconds: float) -> list[str]:
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(video), "-i", str(credit_png)]
    for cap in captions:
        cmd += ["-i", str(cap["png"])]

    # Filter chain: layout -> credit -> each caption shown only during its time.
    parts = [base_filter, f"[v0][1:v]overlay=0:{credit_y}[v1]"]
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
    model_name = os.getenv("WHISPER_MODEL", "small").strip()
    language = os.getenv("WHISPER_LANGUAGE", "en").strip()
    max_seconds = float(os.getenv("MAX_CLIP_SECONDS", "60"))
    layout_setting = os.getenv("LAYOUT", "auto").strip().lower()

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

    # 1. Face + layout
    info = get_video_info(str(video))
    print(f"[1/4] Finding the face in {info['width']}x{info['height']} video...")
    face = find_face(str(video))
    print(f"      {face['detector']} detector saw a face in {face['hits']} of {face['checked']} frames.")
    layout = choose_layout(layout_setting, face, info["width"])
    if layout == "split":
        print("      Layout: SPLIT (facecam on top, gameplay below).")
    elif face["center"]:
        print("      Layout: CROP (one tall slice centered on the face).")
    else:
        print("      Layout: CROP (no face found, using the center of the screen).")

    # 2. Transcribe
    print(f"[2/4] Transcribing speech with Whisper ('{model_name}' model)...")
    print("      (The first time with a new model it downloads it first. Later runs are faster.)")
    words = transcribe_words(str(video), model_name, language or None)
    captions = [c for c in group_words(words) if c["start"] < max_seconds]
    transcript = " ".join(w["text"] for w in words)
    print(f"      Heard: {(transcript[:150] + ('...' if len(transcript) > 150 else '')) or '(no speech)'}")

    # 3. Draw captions + credit as images
    print(f"[3/4] Drawing {len(captions)} captions...")
    caption_center_y = TOP_H if layout == "split" else int(OUT_H * 0.68)
    for i, cap in enumerate(captions):
        cap["png"] = work_dir / f"cap_{i:03d}.png"
        _, h = render_text_png(cap["text"], cap["png"], OUT_W, font_size=86, stroke=7, max_text_width=940)
        cap["y"] = caption_center_y - h // 2
    credit_text = clip["streamer_url"].replace("https://", "")
    credit_png = work_dir / "credit.png"
    render_text_png(credit_text, credit_png, OUT_W, font_size=46, stroke=4, max_text_width=1000)
    credit_y = 30 if layout == "split" else 140

    # 4. Render with ffmpeg
    print("[4/4] Rendering the vertical video with ffmpeg...")
    cmd = build_ffmpeg_command(video, output, base_video_filter(layout, info, face),
                               credit_png, credit_y, captions, max_seconds)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("\nERROR: ffmpeg failed:\n" + result.stderr[-2000:])
        return 1

    # Save an info card for the review step (Phase 4).
    card = dict(clip)
    card.update({
        "edited_file": output.name,
        "layout": layout,
        "transcript": transcript,
        "captions": [{k: c[k] for k in ("text", "start", "end")} for c in captions],
        "face_found": face["center"] is not None,
    })
    (EDITED_DIR / f"{clip['id']}.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(work_dir, ignore_errors=True)

    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"\nDone in {time.time() - started:.0f}s. Saved: {output}  ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
