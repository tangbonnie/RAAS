import numpy as np

from root_crown import repair_microholes, bundle_contact_candidates
from root_topology import Edge


def test_microholes_repaired_and_exact_pixels_audited():
    mask = np.ones((30, 30), dtype=bool)
    mask[10, 10] = False
    mask[15, 15:17] = False
    original = mask.copy()
    result, diagnostic = repair_microholes(mask)
    assert result.all()
    assert diagnostic['repaired_holes'] == 2
    assert diagnostic['repaired_pixels'] == 3
    assert np.array_equal(mask, original)
    changed = {tuple(p) for r in diagnostic['repairs'] for p in r['pixels_rc']}
    assert changed == {(10, 10), (15, 15), (15, 16)}


def test_default_keeps_long_diagonal_slit_and_exterior_notch():
    mask = np.ones((30, 30), dtype=bool)
    mask[np.arange(7, 23), np.arange(7, 23)] = False
    mask[0:2, 25] = False
    result, diagnostic = repair_microholes(mask)
    assert np.array_equal(result, mask)
    assert diagnostic['repaired_holes'] == 0


def test_explicit_four_connected_assumption_is_disclosed():
    mask = np.ones((30, 30), dtype=bool)
    mask[np.arange(7, 23), np.arange(7, 23)] = False
    result, diagnostic = repair_microholes(mask, background_connectivity=4)
    assert result.all()
    assert diagnostic['subpixel_gap_merging_assumed']
    assert diagnostic['repaired_pixels'] == 16


def test_real_gap_and_short_lateral_are_preserved():
    mask = np.zeros((50, 50), dtype=bool)
    mask[10:40, 20:30] = True
    # A short thin lateral must never be removed by a hole operation.
    mask[12, 30:34] = True
    mask[20:23, 23:26] = False
    result, diagnostic = repair_microholes(mask, max_area=16)
    assert np.array_equal(result, mask)
    assert diagnostic['repaired_holes'] == 0


def test_triangular_inter_root_gap_and_long_thin_gap_are_preserved():
    mask = np.ones((50, 50), dtype=bool)
    for row in range(10, 17):
        mask[row, 15:15+row-9] = False
    mask[30, 10:30] = False
    result, diagnostic = repair_microholes(mask, max_area=16)
    assert np.array_equal(result, mask)
    assert diagnostic['repaired_holes'] == 0


def test_bundle_candidates_do_not_mutate_topology_or_classify_as_forks():
    points = {0: np.array([10., 50.]), 1: np.array([50., 50.]),
              2: np.array([95., 40.]), 3: np.array([95., 60.])}
    edges = {i: Edge(u, v, np.linspace(points[u], points[v], 41))
             for i, (u, v) in enumerate([(0, 1), (1, 2), (1, 3)])}
    radius = np.full((110, 110), 3.)
    radius[:45] = 6.
    result = bundle_contact_candidates(edges, points, radius, 0)
    assert len(edges) == 3
    assert len(result) == 1
    assert result[0]['interpretation'] == 'bundle_or_acute_branch'
