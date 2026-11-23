"""
Find where the streamer's face is, so the vertical crop can keep it centered.

How it works (simple version):
  1. Look at ~30 frames spread across the clip, at full resolution (so a small
     facecam in the corner still counts).
  2. In each frame, find faces and keep the most confident / biggest one.
  3. Take the MEDIAN position of those faces (median ignores the odd wrong detection).
  4. If we don't find enough faces, fall back to the middle of the screen.

Face detectors:
  - YuNet (preferred): a small, accurate AI face detector from OpenCV. Good at
    small and turned faces. Downloaded once (~230 KB) into antclipz/models/.
  - Haar cascade (backup): older detector built into OpenCV, used if YuNet
    can't be downloaded.
"""

import statistics
from pathlib import Path

import cv2
import requests

SAMPLE_FRAMES = 30
MIN_DETECTIONS = 3           # need at least this many faces to trust the result
YUNET_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/"
             "face_detection_yunet/face_detection_yunet_2023mar.onnx")
YUNET_PATH = Path(__file__).parent / "models" / "face_detection_yunet_2023mar.onnx"


def get_video_info(video_path: str) -> dict:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    info = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS) or 30.0,
        "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    cap.release()
    return info


def _get_yunet_model() -> Path | None:
    """Download the YuNet model the first time. Returns None if that fails."""
    if YUNET_PATH.exists() and YUNET_PATH.stat().st_size > 100_000:
        return YUNET_PATH
    try:
        response = requests.get(YUNET_URL, timeout=30)
        response.raise_for_status()
        if len(response.content) < 100_000:   # got an error page, not the model
            return None
        YUNET_PATH.parent.mkdir(exist_ok=True)
        YUNET_PATH.write_bytes(response.content)
        return YUNET_PATH
    except requests.RequestException:
        return None


def _make_detector():
    """Returns (name, function that takes a frame and returns (x, y, w, h) boxes)."""
    model = _get_yunet_model()
    if model is not None and hasattr(cv2, "FaceDetectorYN"):
        yunet = cv2.FaceDetectorYN.create(str(model), "", (320, 320), 0.6, 0.3, 5000)

        def detect_yunet(frame):
            h, w = frame.shape[:2]
            yunet.setInputSize((w, h))
            _, faces = yunet.detect(frame)
            if faces is None:
                return []
            # each row: x, y, w, h, ...landmarks..., score -> sort by score
            faces = sorted(faces, key=lambda f: f[-1], reverse=True)
            return [tuple(f[:4]) for f in faces]

        return "YuNet", detect_yunet

    haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def detect_haar(frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = haar.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
        return sorted((tuple(f) for f in faces), key=lambda f: f[2] * f[3], reverse=True)

    return "Haar", detect_haar


def find_face(video_path: str) -> dict:
    """
    Look for the streamer's face. Returns a dict:
      center   -> (x, y) pixel position of the face, or None if not found
      size     -> (width, height) of the face box in pixels, or None
      detector -> "YuNet" or "Haar"
      hits / checked -> frames with a face / frames looked at
    """
    name, detect = _make_detector()
    result = {"center": None, "size": None, "detector": name, "hits": 0, "checked": 0}
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return result

    xs, ys, ws, hs = [], [], [], []
    step = max(total // SAMPLE_FRAMES, 1)
    for frame_no in range(0, total, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ok, frame = cap.read()
        if not ok:
            continue
        result["checked"] += 1
        faces = detect(frame)
        if not faces:
            continue
        x, y, w, h = faces[0]
        xs.append(x + w / 2)
        ys.append(y + h / 2)
        ws.append(w)
        hs.append(h)
    cap.release()

    result["hits"] = len(xs)
    if len(xs) >= MIN_DETECTIONS:
        result["center"] = (statistics.median(xs), statistics.median(ys))
        result["size"] = (statistics.median(ws), statistics.median(hs))
    return result


def _even(n: float) -> int:
    return int(n) // 2 * 2


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def split_layout_boxes(width: int, height: int, face_center: tuple[float, float],
                       face_size: tuple[float, float], top_aspect: float,
                       bottom_aspect: float) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """
    For "game + small facecam" streams. Returns two crop boxes (w, h, x, y):
      cam  -> a box around the face (guessing the facecam area), for the TOP panel
      game -> a tall slice of the gameplay, for the BOTTOM panel
    aspect = width / height of each output panel.
    """
    fx, fy = face_center
    face_w = face_size[0]

    # Facecam guess: about 5.5 face-widths wide, shaped like the top panel.
    cam_w = _even(_clamp(face_w * 5.5, 320, width))
    cam_h = _even(min(cam_w / top_aspect, height))
    cam_w = _even(cam_h * top_aspect)
    cam_x = _even(_clamp(fx - cam_w / 2, 0, width - cam_w))
    cam_y = _even(_clamp(fy - cam_h / 2, 0, height - cam_h))

    # Gameplay: full height, as wide as the bottom panel shape allows.
    game_h = _even(height)
    game_w = _even(min(game_h * bottom_aspect, width))
    # Try centered, right of the facecam, and left of it; pick the one that
    # overlaps the facecam least (so Kai doesn't show up twice). Ties -> centered.
    candidates = [
        _clamp(width / 2 - game_w / 2, 0, width - game_w),
        _clamp(cam_x + cam_w, 0, width - game_w),
        _clamp(cam_x - game_w, 0, width - game_w),
    ]

    def overlap(gx: float) -> float:
        return max(0.0, min(gx + game_w, cam_x + cam_w) - max(gx, cam_x))

    game_x = _even(min(candidates, key=overlap))
    return (cam_w, cam_h, cam_x, cam_y), (game_w, game_h, game_x, 0)


def vertical_crop_box(width: int, height: int, face: tuple[float, float] | None) -> tuple[int, int, int, int]:
    """
    Work out the 9:16 rectangle to cut out of the original video.
    Returns (crop_width, crop_height, x, y). Numbers are kept even because
    the H.264 video format requires even sizes.
    """
    target = 9 / 16
    if width / height > target:
        # Normal case: wide 16:9 stream -> keep full height, cut a narrow slice.
        crop_h = height - height % 2
        crop_w = int(crop_h * target) // 2 * 2
        center_x = face[0] if face else width / 2
        x = int(min(max(center_x - crop_w / 2, 0), width - crop_w)) // 2 * 2
        return crop_w, crop_h, x, 0
    # Already tall (rare): keep full width, cut height around the face.
    crop_w = width - width % 2
    crop_h = int(crop_w / target) // 2 * 2
    center_y = face[1] if face else height / 2
    y = int(min(max(center_y - crop_h / 2, 0), height - crop_h)) // 2 * 2
    return crop_w, crop_h, 0, y
