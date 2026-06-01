"""Frame detection + perspective rectification.

The detection scaffold is a solid black border frame. Binarize, find the largest
frame-like contour (a big top-level region enclosing a hole), approximate its four
outer corners, map them onto the canonical frame corners, and warp the panel back to
its canonical frame.
"""

from __future__ import annotations

import cv2
import numpy as np

from noircode.config import Config
from noircode.geometry import layout


class DetectError(RuntimeError):
    """Raised when the border frame cannot be located."""


def _to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Order four points as TL, TR, BR, BL."""
    s = pts.sum(axis=1)
    d = pts[:, 0] - pts[:, 1]
    return np.array(
        [
            pts[int(np.argmin(s))],  # TL
            pts[int(np.argmax(d))],  # TR
            pts[int(np.argmax(s))],  # BR
            pts[int(np.argmin(d))],  # BL
        ],
        dtype=np.float32,
    )


def _quad(contour: np.ndarray) -> np.ndarray | None:
    """Approximate a contour to a 4-point quadrilateral, or None."""
    peri = cv2.arcLength(contour, True)
    for eps in (0.02, 0.03, 0.05, 0.08):
        approx = cv2.approxPolyDP(contour, eps * peri, True)
        if len(approx) == 4:
            return approx.reshape(4, 2).astype(np.float32)
    return None


def _dedup_quads(quads: list[np.ndarray], tol: float = 12.0) -> list[np.ndarray]:
    """Drop quads whose corners nearly coincide with one already kept."""
    kept: list[np.ndarray] = []
    for q in quads:
        oq = _order_corners(q)
        if any(float(np.abs(_order_corners(k) - oq).max()) <= tol for k in kept):
            continue
        kept.append(oq)
    return kept


def detect_frames(img: np.ndarray, max_candidates: int = 6) -> list[np.ndarray]:
    """Return candidate frame quads (corners ordered TL, TR, BR, BL), largest first.

    A screenshot/photo can nest the panel inside other dark rings (window chrome, an
    outer screenshot border). The true panel frame is usually NOT the largest ring, so
    return several candidates and let the caller pick the one that decodes (CRC-checked).
    """
    gray = _to_gray(img)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, hierarchy = cv2.findContours(bw, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return []
    hier = hierarchy[0]
    area_img = float(gray.shape[0] * gray.shape[1])

    scored: list[tuple[float, np.ndarray]] = []
    for i, contour in enumerate(contours):
        parent, first_child = hier[i][3], hier[i][2]
        if parent != -1 or first_child == -1:
            continue  # a frame is a top-level ring: encloses a hole
        area = cv2.contourArea(contour)
        if area < area_img * 0.05:
            continue
        quad = _quad(contour)
        if quad is not None:
            scored.append((area, quad))

    scored.sort(key=lambda t: t[0], reverse=True)
    return _dedup_quads([q for _, q in scored])[:max_candidates]


def detect_frame(img: np.ndarray) -> np.ndarray:
    """Return the most prominent frame's four outer corners (TL, TR, BR, BL)."""
    frames = detect_frames(img, max_candidates=1)
    if not frames:
        raise DetectError("no frame-like quadrilateral found")
    return frames[0]


def rectify_with(img: np.ndarray, cfg: Config, corners: np.ndarray) -> np.ndarray:
    """Warp the panel to canonical using the given (ordered) frame corners."""
    panel = layout(cfg)
    dst = np.array(panel.frame_corners, dtype=np.float32)
    transform = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
    return cv2.warpPerspective(_to_gray(img), transform, (panel.width, panel.height))


def rectify_panel(img: np.ndarray, cfg: Config) -> np.ndarray:
    """Locate the frame and warp the whole panel back to its canonical frame."""
    return rectify_with(img, cfg, detect_frame(img))


def detect_and_rectify(img: np.ndarray, cfg: Config) -> np.ndarray:
    """Locate the frame, rectify, and crop just the Channel A grid region."""
    x0, y0, x1, y1 = layout(cfg).grid_box
    return rectify_panel(img, cfg)[y0:y1, x0:x1]
