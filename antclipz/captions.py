"""
Captions: turn speech into text with Whisper, then draw the text as images.

- Transcription uses "faster-whisper", a free version of OpenAI Whisper that
  runs on your own PC (no API key, no cost). The first run downloads the model
  (base model is about 150 MB) and then reuses it.
- Each caption is drawn as a transparent PNG with Pillow (white bold text with a
  black outline, TikTok style). ffmpeg then layers those PNGs onto the video at
  the right times. Drawing them ourselves works on every ffmpeg build.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf",                          # Windows: Arial Bold
    r"C:\Windows\Fonts\impact.ttf",                           # Windows: Impact
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",   # Linux
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",      # Mac
]

MAX_WORDS_PER_CAPTION = 3
MAX_CAPTION_SECONDS = 1.5
PAUSE_SPLIT_SECONDS = 0.6


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def transcribe_words(video_path: str, model_name: str = "base", language: str | None = "en") -> list[dict]:
    """Return every spoken word with its start/end time in seconds."""
    from faster_whisper import WhisperModel  # imported here because it is slow to load

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(
        video_path,
        language=language or None,
        word_timestamps=True,
        vad_filter=True,   # skip silent parts
    )
    words = []
    for segment in segments:
        for w in segment.words or []:
            text = w.word.strip()
            if text:
                words.append({"text": text, "start": round(w.start, 2), "end": round(w.end, 2)})
    return words


def group_words(words: list[dict]) -> list[dict]:
    """Group words into short punchy captions of 1-3 words."""
    captions: list[dict] = []
    current: list[dict] = []
    for word in words:
        if current:
            too_many = len(current) >= MAX_WORDS_PER_CAPTION
            too_long = word["end"] - current[0]["start"] > MAX_CAPTION_SECONDS
            paused = word["start"] - current[-1]["end"] > PAUSE_SPLIT_SECONDS
            if too_many or too_long or paused:
                captions.append(_finish(current))
                current = []
        current.append(word)
    if current:
        captions.append(_finish(current))

    # Make each caption stay up until the next one starts (no flicker), max +0.5s.
    for i in range(len(captions) - 1):
        gap_end = min(captions[i + 1]["start"], captions[i]["end"] + 0.5)
        captions[i]["end"] = max(captions[i]["end"], gap_end)
    return captions


def _finish(words: list[dict]) -> dict:
    return {
        "text": " ".join(w["text"] for w in words).upper(),
        "start": words[0]["start"],
        "end": words[-1]["end"],
    }


def render_text_png(text: str, out_path: Path, width: int, font_size: int,
                    stroke: int, max_text_width: int) -> tuple[int, int]:
    """Draw centered, outlined text on a transparent image. Returns (width, height)."""
    font = load_font(font_size)
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    # Wrap words onto multiple lines if they are too wide.
    lines: list[str] = []
    for word in text.split():
        trial = f"{lines[-1]} {word}" if lines else word
        if lines and measure.textlength(trial, font=font) <= max_text_width:
            lines[-1] = trial
        else:
            lines.append(word)

    line_height = int(font_size * 1.2)
    height = line_height * len(lines) + stroke * 2 + 10
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text(
            (width / 2, stroke + 5 + i * line_height),
            line, font=font, anchor="ma",
            fill="white", stroke_width=stroke, stroke_fill="black",
        )
    image.save(out_path)
    return width, height
