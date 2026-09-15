"""Independent pixel fixtures for the opt-in proximal photographic repair."""
import numpy as np
import pytest
from skimage.morphology import skeletonize

from root_stem import repair_proximal_stem
from root_topology import analyze_topology


def porous_stem():
    mask = np.zeros((360, 220), bool)
    mask[20:330, 90:130] = True
    mask[29:35, 98:104] = False
    mask[41:48, 116:121] = False
    mask[58:66, 104:111] = False
    return mask


def test_disabled_mode_preserves_input_and_reports_no_inference():
    source = porous_stem()
    result, info, added = repair_proximal_stem(source)
    assert np.array_equal(result, source)
    assert not added.any()
    assert info['status'] == 'disabled'


def test_fill_enclosed_photographic_pores_and_keep_exact_pixel_audit():
    source = porous_stem()
    old = source.copy()
    result, info, added = repair_proximal_stem(source, enabled=True)
    assert info['status'] == 'applied'
    assert info['filled_holes'] == 3
    assert result[20:100, 90:130].all()
    assert np.array_equal(source, old)
    assert np.array_equal(result ^ source, added)
    assert info['added_pixels'] == 36 + 35 + 56
    r0, c0, r1, c1 = info['roi_rc']
    outside = np.ones_like(source)
    outside[r0:r1, c0:c1] = False
    assert np.array_equal(result[outside], source[outside])
    assert np.all(result[source])
    before = analyze_topology(skeletonize(source), binary=source, crossing_context=False)
    after = analyze_topology(skeletonize(result), binary=result, crossing_context=False)
    assert before['num_forks'] > 0
    assert after['num_forks'] == 0
    assert after['num_tips'] == 1


def test_exterior_slot_and_fine_lateral_are_not_bridged():
    source = porous_stem()
    # An exterior-connected cut, not an enclosed photographic pore.
    source[76:80, 112:130] = False
    # A real thin lateral below the conservative terminal ROI.
    source[121:124, 128:185] = True
    result, info, added = repair_proximal_stem(source, enabled=True)
    assert info['status'] == 'applied'
    assert not result[76:80, 112:130].any()
    assert np.array_equal(result[100:], source[100:])
    after = analyze_topology(skeletonize(result), binary=result, crossing_context=False)
    tips = np.asarray(after['tip_coords'])
    assert np.min(np.linalg.norm(tips - [122, 183], axis=1)) <= 3


def test_short_real_lateral_tip_survives_quantification():
    source = porous_stem()
    source[110:113, 129:140] = True
    result, _, _ = repair_proximal_stem(source, enabled=True)
    before = analyze_topology(skeletonize(source), binary=source, crossing_context=False)
    after = analyze_topology(skeletonize(result), binary=result, crossing_context=False)
    for topology in (before, after):
        tips = np.asarray(topology['tip_coords'])
        assert np.min(np.linalg.norm(tips - [111, 138], axis=1)) <= 3


def test_open_gap_inside_accepted_roi_is_preserved():
    source = porous_stem()
    # The cut face contains a narrow slot opening directly to the outside.
    # Its complete depth lies inside the proposed repair region. This tests
    # exterior connectivity rather than merely placing a gap outside the ROI.
    source[20:76, 112:114] = False
    result, info, added = repair_proximal_stem(source, enabled=True)
    assert info['status'] == 'applied'
    assert info['roi_rc'][0] <= 20 and info['roi_rc'][2] >= 76
    assert not result[20:76, 112:114].any()
    assert not added[20:76, 112:114].any()
    assert result[29:35, 98:104].all()


@pytest.mark.parametrize('turns,direction', [(0, 'top'), (1, 'left'), (2, 'bottom'), (3, 'right')])
def test_direction_equivariance(turns, direction):
    source = porous_stem()
    reference, _, reference_added = repair_proximal_stem(source, enabled=True)
    rotated = np.rot90(source, turns)
    actual, info, added = repair_proximal_stem(rotated, direction, enabled=True)
    assert info['status'] == 'applied'
    assert np.array_equal(actual, np.rot90(reference, turns))
    assert np.array_equal(added, np.rot90(reference_added, turns))


def test_thin_wire_pointed_fan_single_loop_and_small_noise_unchanged():
    wire = np.zeros((360, 220), bool)
    wire[20:330, 108:113] = True
    wire[50:54, 110] = False
    fan = np.zeros_like(wire)
    for row in range(20, 330):
        half = min(90, (row - 20) // 3 + 1)
        fan[row, 110 - half:111 + half] = True
    fan[38:43, 108:112] = False
    fan[47:52, 115:119] = False
    fan[62:67, 102:108] = False
    single_loop = np.zeros_like(wire)
    single_loop[20:330, 90:130] = True
    single_loop[35:65, 98:122] = False
    noise = np.zeros_like(wire)
    noise[20:50, 90:130] = True
    for source in (wire, fan, single_loop, noise):
        result, info, added = repair_proximal_stem(source, enabled=True)
        assert info['status'] == 'not_applied'
        assert np.array_equal(result, source)
        assert not added.any()


def test_large_true_gap_with_small_pores_stays_ambiguous():
    source = porous_stem()
    source[40:67, 96:124] = False
    source[70:73, 100:103] = False
    source[76:79, 119:122] = False
    result, info, added = repair_proximal_stem(source, enabled=True)
    assert info['status'] == 'not_applied'
    assert np.array_equal(result, source)
    assert not added.any()


def test_missing_direction_and_invalid_inputs():
    source = porous_stem()
    result, info, _ = repair_proximal_stem(source, 'none', enabled=True)
    assert np.array_equal(result, source)
    assert info['reason'] == 'proximal_direction_required'
    with pytest.raises(ValueError):
        repair_proximal_stem(np.zeros((0, 0)), enabled=True)
    with pytest.raises(ValueError):
        repair_proximal_stem(source, 'diagonal', enabled=True)
