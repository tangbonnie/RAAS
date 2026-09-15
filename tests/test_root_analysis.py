"""
Unit tests for root_analysis.py — fractal / skan / Strahler.

Strategy
--------
Each test constructs a *known* binary/skeleton shape with an analytically known
answer, then asserts the implementation reproduces it. We avoid calling any
external CSV/image.

Shapes
------
- Solid square          → FD ≈ 2.0 (Euclidean 2D fill)
- Solid line            → FD ≈ 1.0 (Euclidean 1D)
- Single straight line  → tips=1, forks=0, crossings=0, Strahler max=1
- Y-junction            → tips=2, forks=1, crossings=0, junctions=1, Strahler=2
- X-crossing (T-pair)   → After cross_merge_mm merge, should count as 1 crossing
                          and 0 forks; sensitive to cross_merge_mm parameter.

Runner
------
    pytest tests/ -v
"""
import numpy as np
import pytest

from root_analysis import (
    compute_fractal_dimension,
    compute_multifractal_spectrum,
    skan_analyze,
)


def test_uniform_square_has_narrow_multifractal_spectrum():
    """A uniform square is monofractal; q=1 must not create a spectrum spike."""
    # Restrict q to avoid negative-q amplification of partial boundary boxes.
    result = compute_multifractal_spectrum(
        np.ones((256, 256), dtype=bool), q_range=(0, 2), q_num=5, min_box=16, num_sizes=3)
    for key in ('D0', 'D1', 'D2'):
        assert abs(result[key] - 2.0) < 0.1
    assert result['Delta_alpha'] < 0.15


# ---------------------------------------------------------------------------
# Fractal dimension
# ---------------------------------------------------------------------------
def test_fractal_dimension_solid_square_is_near_2():
    """A fully filled square is a 2D Euclidean object → FD should be ~2.0."""
    img = np.ones((512, 512), dtype=bool)
    FD, FA, R2 = compute_fractal_dimension(img)
    # Box-counting on a filled square: N(ε) = (L/ε)^2, so slope = 2 exactly.
    # Finite-size effects give ~1.95–2.05 tolerance.
    assert 1.90 < FD < 2.05, f"Expected FD≈2.0 for solid square, got {FD:.3f}"
    # R² should be very high — solid square is perfectly self-similar.
    assert R2 > 0.995, f"Expected R²>0.995 on clean shape, got {R2:.4f}"


def test_fractal_dimension_straight_line_is_near_1():
    """A 1D straight line → FD ≈ 1.0 (Euclidean 1D)."""
    img = np.zeros((512, 512), dtype=bool)
    img[256, :] = True  # single horizontal line
    FD, _, R2 = compute_fractal_dimension(img)
    assert 0.90 < FD < 1.10, f"Expected FD≈1.0 for line, got {FD:.3f}"
    assert R2 > 0.99, f"Expected R²>0.99 on clean line, got {R2:.4f}"


# ---------------------------------------------------------------------------
# Helpers for constructing synthetic skeletons
# ---------------------------------------------------------------------------
def _make_straight_skeleton(length=200):
    """A single horizontal 1-pixel line, well padded."""
    img = np.zeros((length + 40, length + 40), dtype=bool)
    img[20 + length // 2, 20:20 + length] = True
    return img


def _make_y_skeleton():
    """A Y-shaped skeleton: one vertical stem and two diagonal arms.

    Topology: 3 tips (two arm-ends + one stem-end), 1 fork, 0 crossings.
    """
    img = np.zeros((200, 200), dtype=bool)
    # vertical stem from (20,100) down to (100,100)
    img[20:101, 100] = True
    # two arms from (100,100) diagonally outward
    for i in range(60):
        if 100 + i < 200 and 100 + i < 200:
            img[100 + i, 100 + i] = True   # SE arm
        if 100 + i < 200 and 100 - i >= 0:
            img[100 + i, 100 - i] = True   # SW arm
    return img


def _make_x_crossing_skeleton(sep_px=4):
    """Two lines crossing as a T-pair: skeletonize splits X into two adjacent
    degree-3 nodes connected by a short edge of length `sep_px`. With
    cross_merge_mm large enough that sep_px < merge_px, they merge to 1 crossing.
    """
    img = np.zeros((200, 200), dtype=bool)
    # two nearly-horizontal lines meeting at two T-nodes
    #   --- top bar from (95, 30) to (95, 170) split into two rails
    # Instead: simulate skeletonize X→T-T by two parallel horizontal lines
    # with short vertical linker between them
    img[95, 30:95 + 1] = True        # left rail of top
    img[95, 95 + sep_px:170] = True  # left rail continues on far side? no.
    # Simpler recipe: build H shape that has exactly 2 degree-3 nodes `sep_px` apart
    # Left vertical bar + right vertical bar + short horizontal link
    img[:, :] = False
    img[30:170, 90] = True                        # left vertical line
    img[30:170, 90 + sep_px] = True               # right vertical line
    img[100, 90:90 + sep_px + 1] = True           # horizontal link
    return img


# ---------------------------------------------------------------------------
# skan topology
# ---------------------------------------------------------------------------
def test_skan_straight_line_topology():
    """A rooted single line should have 1 tip, 0 forks, 0 crossings, 0 junctions."""
    skel = _make_straight_skeleton(length=150)
    sa = skan_analyze(skel, dpi=300)
    assert sa['num_tips'] == 1, f"tips={sa['num_tips']}"
    assert sa['num_forks'] == 0, f"forks={sa['num_forks']}"
    assert sa['num_crossings'] == 0, f"crossings={sa['num_crossings']}"
    assert sa['num_junctions'] == 0, f"junctions={sa['num_junctions']}"
    # Root length should be ≈ (150 px) × (2.54 cm / 300 dpi)
    expected_cm = 150 * 2.54 / 300
    assert abs(sa['root_length_cm'] - expected_cm) < 0.05


def test_skan_y_junction_topology():
    """Y-shape: 2 tips, 1 fork, 0 crossings, 1 junction."""
    skel = _make_y_skeleton()
    sa = skan_analyze(skel, dpi=300)
    assert sa['num_tips'] == 2, f"Expected 2 tips, got {sa['num_tips']}"
    assert sa['num_forks'] == 1, f"Expected 1 fork, got {sa['num_forks']}"
    assert sa['num_crossings'] == 0, f"Expected 0 crossings, got {sa['num_crossings']}"
    assert sa['num_junctions'] == 1, f"Expected 1 junction, got {sa['num_junctions']}"
    # Strahler of a Y is exactly 2 (two 1-order tips merge to 2-order)
    assert sa['strahler']['Strahler_Max_Order'] == 2


def test_two_nearby_parallel_roots_are_not_a_crossing():
    # The previous test called this H shape an X solely because it was small.
    # Parallel rails do not establish a crossing of two nonparallel axes.
    sa = skan_analyze(_make_x_crossing_skeleton(sep_px=10), dpi=300)
    assert sa['num_crossings'] == 0
    assert sa['num_forks'] == 2
