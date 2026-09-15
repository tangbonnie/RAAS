"""Intensity-supported segmentation of roots on a reasonably uniform background.

Every accepted pixel must have observed intensity support. No closing, hole
filling or border erosion is used: those operations change root topology.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from skimage import color, filters, util


def segment_root_intensity(image, foreground="auto", low_ratio=0.5,
                           min_component_area=8):
    """Return ``(mask, diagnostics)`` using intensity hysteresis.

    Strong pixels exceed Otsu's threshold. Connected weaker pixels down to
    ``low_ratio`` of that contrast are retained to preserve dim fine roots.
    This is a *segmentation*, not a reconstruction of invisible roots. The
    thresholds and retained weak-pixel fraction are returned for review.
    Appropriate for a dark or light uniform background, not soil photographs.
    """
    if foreground not in {"auto", "light", "dark"}:
        raise ValueError("foreground must be auto, light or dark")
    if not 0 < low_ratio <= 1:
        raise ValueError("low_ratio must be in (0, 1]")
    arr = np.asarray(image)
    if arr.ndim == 3:
        arr = color.rgb2gray(arr[..., :3])
    if arr.ndim != 2 or not arr.size:
        raise ValueError("expected a nonempty grayscale or RGB image")
    gray = util.img_as_float32(arr)
    if not np.isfinite(gray).all() or gray.min() < 0 or gray.max() > 1:
        raise ValueError("floating image intensities must be finite in [0, 1]")
    # Sample an area, not just the outermost pixel: scanner rims can have a
    # different brightness from the actual background across an entire edge.
    rim = max(1, min(gray.shape) // 100)
    edge = np.concatenate((gray[:rim].ravel(), gray[-rim:].ravel(),
                           gray[:, :rim].ravel(), gray[:, -rim:].ravel()))
    if foreground == "auto":
        foreground = "light" if np.median(edge) < 0.5 else "dark"
    signal = gray if foreground == "light" else 1.0 - gray
    edge_signal = edge if foreground == "light" else 1.0 - edge
    background = float(np.median(edge_signal))
    noise_mad = float(np.median(np.abs(edge_signal - background)))
    peak = float(signal.max())
    if peak <= background + 1e-6:
        return np.zeros(gray.shape, bool), {
            "foreground": foreground, "strong_threshold": peak,
            "weak_threshold": peak, "weak_retained_fraction": 0.0,
            "foreground_pixels": 0, "component_count": 0,
            "border_foreground_pixels": 0,
        }
    high = float(filters.threshold_otsu(signal))
    high = max(high, background + 1e-6)
    low = max(background + low_ratio * (high - background),
              background + 4.0 * 1.4826 * noise_mad)
    low = min(low, high)
    strong = signal > high
    weak = signal > low
    structure = np.ones((3, 3), bool)
    labels, n = ndimage.label(weak, structure=structure)
    sizes = np.bincount(labels.ravel())
    seeded = np.bincount(labels[strong], minlength=n + 1) > 0
    accepted = seeded & (sizes >= max(1, int(min_component_area)))
    accepted[0] = False
    mask = accepted[labels]
    foreground_count = int(mask.sum())
    border_count = int(mask[0].sum() + mask[-1].sum() +
                       mask[1:-1, 0].sum() + mask[1:-1, -1].sum())
    return mask, {
        "foreground": foreground,
        "strong_threshold": high, "weak_threshold": float(low),
        "weak_retained_fraction": float((mask & ~strong).sum()) /
                                  max(1, foreground_count),
        "foreground_pixels": foreground_count,
        "component_count": int(accepted.sum()),
        "border_foreground_pixels": border_count,
        "rejected_weak_pixels": int((weak & ~mask).sum()),
    }
