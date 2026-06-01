"""Synthetic capture & damage simulation (shared by the eval harness and tests).

Lets the system be exercised without a physical camera: perspective warp, blur,
noise, occlusion patches and JPEG compression. All deterministic given a seeded
``numpy.random.Generator``.
"""

from __future__ import annotations

import cv2
import numpy as np

from noircode.config import Config
from noircode.geometry import layout


def warp_panel(
    panel: np.ndarray,
    rng: np.random.Generator,
    *,
    max_shift_frac: float = 0.06,
    pad: int = 48,
    blur: int = 3,
    noise_sigma: float = 4.0,
) -> np.ndarray:
    """Pad, perspective-warp, blur and add Gaussian noise to a canonical panel."""
    h, w = panel.shape
    canvas = np.full((h + 2 * pad, w + 2 * pad), 255, dtype=np.uint8)
    canvas[pad : pad + h, pad : pad + w] = panel

    src = np.array(
        [[pad, pad], [pad + w, pad], [pad + w, pad + h], [pad, pad + h]], dtype=np.float32
    )
    shift = max_shift_frac * min(w, h)
    dst = (src + rng.uniform(-shift, shift, src.shape)).astype(np.float32)
    transform = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(
        canvas, transform, (canvas.shape[1], canvas.shape[0]), borderValue=255
    )

    if blur:
        out = cv2.GaussianBlur(out, (blur, blur), 0)
    if noise_sigma:
        noisy = out.astype(np.float32) + rng.normal(0, noise_sigma, out.shape)
        out = np.clip(noisy, 0, 255).astype(np.uint8)
    return out


def occlude_grid(
    panel: np.ndarray,
    cfg: Config,
    rng: np.random.Generator,
    coverage: float,
    *,
    fill: int = 0,
) -> np.ndarray:
    """Paint opaque patches over ~``coverage`` of the grid region (finders untouched)."""
    p = layout(cfg)
    x0, y0, x1, y1 = p.grid_box
    gw, gh = x1 - x0, y1 - y0
    out = panel.copy()
    target = coverage * gw * gh
    painted = 0.0
    while painted < target:
        pw = int(rng.integers(gw // 10, gw // 3 + 1))
        ph = int(rng.integers(gh // 10, gh // 3 + 1))
        px = x0 + int(rng.integers(0, max(1, gw - pw)))
        py = y0 + int(rng.integers(0, max(1, gh - ph)))
        out[py : py + ph, px : px + pw] = fill
        painted += pw * ph
    return out


def jpeg(img: np.ndarray, quality: int) -> np.ndarray:
    """Round-trip through JPEG at the given quality (0-100)."""
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    assert ok
    decoded = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    assert decoded is not None
    return decoded
