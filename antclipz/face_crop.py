"""
Find where the streamer's face is, so the vertical crop can keep it centered.

How it works (simple version):
  1. Look at ~30 frames spread across the clip.
  2. In each frame, find faces with OpenCV's built-in face detector and keep the biggest one.
  3. Take the MEDIAN position of those faces (median ignores the odd wrong detection).
  4. If we don't find enough faces, fall back to the middle of the screen.
"""

import statistics

import cv2

SAMPLE_FRAMES = 30
DETECT_WIDTH = 640           # shrink frames to this width first, so detection is fast
MIN_DETECTIONS = 3           # need at least this many faces to trust the result


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


def find_face_center(video_path: str) -> tuple[float, float] | None:
    """Return the (x, y) pixel position of the streamer's face, or None if not found."""
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return None

    xs, ys = [], []
    step = max(total // SAMPLE_FRAMES, 1)
    for frame_no in range(0, total, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ok, frame = cap.read()
        if not ok:
            continue
        scale = DETECT_WIDTH / frame.shape[1]
        small = cv2.resize(frame, None, fx=scale, fy=scale)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(30, 30))
        if len(faces) == 0:
            continue
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])  # biggest face
        xs.append((x + w / 2) / scale)
        ys.append((y + h / 2) / scale)
    cap.release()

    if len(xs) < MIN_DETECTIONS:
        return None
    return statistics.median(xs), statistics.median(ys)


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
