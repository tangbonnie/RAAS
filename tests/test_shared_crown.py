"""Shared-crown reconstruction against independently rasterized root cylinders."""

import numpy as np
import pytest
from scipy.ndimage import binary_fill_holes
from scipy.optimize import linear_sum_assignment

from root_topology import analyze_topology, measure_paths
from tests.accuracy_phantoms import render, truth


def _straight_fan(count, length, diameter, gap_degrees):
    # Input geometry is specified before rasterization, independently of the graph.
    angles = np.deg2rad((np.arange(count) - (count - 1) / 2) * gap_degrees)
    half_width = length * np.max(np.abs(np.sin(angles))) + 30
    origin = np.array([np.ceil(half_width), 30.0])  # render uses (x, y).
    ends = origin + length * np.column_stack((np.sin(angles), np.cos(angles)))
    segments = [(origin, end, diameter) for end in ends]
    size = (int(2 * origin[0] + 1), int(np.ceil(length + 61)))
    return segments, size, origin


def _match_points(actual, expected, tolerance):
    actual, expected = np.asarray(actual), np.asarray(expected)
    assert actual.shape == expected.shape
    distances = np.linalg.norm(actual[:, None, :] - expected[None, :, :], axis=-1)
    rows, columns = linear_sum_assignment(distances)
    assert np.max(distances[rows, columns]) <= tolerance


@pytest.mark.parametrize(
    'count,length,diameter,gap_degrees',
    [(4, 300.0, 7.0, 4.0), (8, 460.0, 9.0, 2.5), (16, 620.0, 9.0, 2.0)],
    ids=['four_roots', 'eight_roots_long_contact', 'sixteen_roots_long_contact'],
)
def test_shared_crown_recovers_independent_straight_root_geometry(
    count, length, diameter, gap_degrees
):
    segments, size, origin = _straight_fan(count, length, diameter, gap_degrees)
    # Rectangles sharing an origin have a star-shaped, hole-free continuous union.
    # Majority pixel sampling can close subpixel separation slots into tiny holes;
    # remove only those raster artifacts in this analytically hole-free fixture.
    # The actual cycle rejection fixture below intentionally remains unfilled.
    mask = binary_fill_holes(render(segments, size=size))
    expected = truth(segments)
    kwargs = dict(binary=mask, base_rc=origin[::-1], root_direction='top')

    general = analyze_topology(mask, root_model='general', **kwargs)
    shared = analyze_topology(mask, root_model='shared_crown', **kwargs)
    original_measurement = measure_paths(general['_resolved_edges'], mask)
    reconstructed_measurement = measure_paths(shared['_resolved_edges'], mask)

    assert shared['reconstruction']['status'] == 'applied'
    assert shared['topology_status'] == 'model_assumed'
    assert shared['num_root_paths'] == count
    assert shared['num_tips'] == general['num_tips'] == count
    assert shared['num_forks'] == 0
    assert len(shared['_resolved_edges']) == count

    # Reconstruction must retain the observed terminals, not manufacture a count.
    _match_points(shared['tip_coords'], general['tip_coords'], tolerance=1e-7)
    _match_points(
        shared['tip_coords'],
        [np.asarray(end)[::-1] for _, end, _ in segments],
        tolerance=max(2.0, diameter * 0.5),
    )
    shared_ends = [edge.path[-1] for edge in shared['_resolved_edges'].values()]
    shared_starts = [edge.path[0] for edge in shared['_resolved_edges'].values()]
    # Accept either orientation of an Edge, but each must connect base to a tip.
    base = np.asarray(shared['base_coords'][0])
    distal = []
    for start, end in zip(shared_starts, shared_ends):
        if np.linalg.norm(start - base) <= 1e-7:
            distal.append(end)
        else:
            assert np.linalg.norm(end - base) <= 1e-7
            distal.append(start)
    _match_points(distal, shared['tip_coords'], tolerance=1e-7)

    for edge in shared['_resolved_edges'].values():
        inferred = np.asarray(edge.inferred_mask)
        assert inferred.dtype == np.bool_
        assert inferred.shape == (len(edge.path),)
        assert inferred.any(), 'Every root traverses the shared proximal contact.'
        assert (~inferred).any(), 'Separated distal sections remain directly observed.'

    assert 0 < reconstructed_measurement['path_inferred_length_fraction'] < 1
    assert shared['projected_length_px'] == pytest.approx(
        general['root_length_px'], rel=1e-8
    )
    assert reconstructed_measurement['length_px'] > shared['projected_length_px']

    # Targets come from the continuous cylinders, never from the skeleton graph.
    tolerances = {'length_px': 0.05, 'diameter_px': 0.07, 'volume_px3': 0.15}
    for field, tolerance in tolerances.items():
        actual = reconstructed_measurement[field]
        assert actual == pytest.approx(expected[field], rel=tolerance), field
        original_error = abs(original_measurement[field] / expected[field] - 1)
        reconstructed_error = abs(actual / expected[field] - 1)
        assert reconstructed_error < original_error, (
            f'{field}: reconstruction error {reconstructed_error:.3%} did not '
            f'improve on projected-graph error {original_error:.3%}'
        )


@pytest.fixture
def temporary_png_paths():
    # Use temporary files without pytest's platform-specific /tmp basetemp.
    from pathlib import Path
    from uuid import uuid4

    directory = Path(__file__).resolve().parents[1] / 'results'
    directory.mkdir(exist_ok=True)
    prefix = 'test_shared_crown_' + uuid4().hex
    paths = directory / f'{prefix}.png', directory / f'{prefix}_skeleton.png'
    try:
        yield paths
    finally:
        for path in paths:
            path.unlink(missing_ok=True)


def test_image_entrypoint_preserves_shared_crown_results(temporary_png_paths):
    from PIL import Image
    from skimage.morphology import skeletonize
    from root_analysis import analyze_root_image

    segments, size, origin = _straight_fan(4, 300.0, 7.0, 4.0)
    mask = binary_fill_holes(render(segments, size=size))
    skeleton = skeletonize(mask)
    binary_path, skeleton_path = temporary_png_paths
    Image.fromarray(mask.astype(np.uint8) * 255).save(binary_path)
    Image.fromarray(skeleton.astype(np.uint8) * 255).save(skeleton_path)
    kwargs = dict(base_rc=origin[::-1], root_direction='top', root_model='shared_crown')

    core = analyze_topology(skeleton, binary=mask, **kwargs)
    core_measurement = measure_paths(core['_resolved_edges'], mask)
    product = analyze_root_image(binary_path, skeleton_path, **kwargs)

    assert product['Root_Model'] == core['root_model'] == 'shared_crown'
    assert product['Root_Reconstruction_Status'] == core['reconstruction']['status'] == 'applied'
    assert product['Topology_Status'] == core['topology_status'] == 'model_assumed'
    assert product['Num_Reconstructed_Root_Paths'] == core['num_root_paths'] == 4
    assert product['Projected_Path_Length_px'] == pytest.approx(
        core['projected_length_px'], rel=1e-8
    )
    assert product['Path_Inferred_Length_Fraction'] == pytest.approx(
        core_measurement['path_inferred_length_fraction'], rel=1e-8
    )
    assert product['Root_Length_px'] == pytest.approx(core['root_length_px'], rel=1e-8)


def test_shared_crown_preserves_mixed_root_diameters():
    segments, size, origin = _straight_fan(4, 350.0, 9.0, 4.0)
    # Unequal lengths make width assignment affect the aggregate truth as well.
    lengths, diameters = [260.0, 290.0, 320.0, 350.0], [5.0, 7.0, 9.0, 11.0]
    segments = [
        (origin, origin + (end - origin) * root_length / 350.0, diameter)
        for (_, end, _), root_length, diameter in zip(segments, lengths, diameters)
    ]
    mask = binary_fill_holes(render(segments, size=size))
    expected = truth(segments)
    kwargs = dict(binary=mask, base_rc=origin[::-1], root_direction='top')

    general = analyze_topology(mask, root_model='general', **kwargs)
    shared = analyze_topology(mask, root_model='shared_crown', **kwargs)
    original = measure_paths(general['_resolved_edges'], mask)
    recovered, profiles = measure_paths(shared['_resolved_edges'], mask, return_profiles=True)

    assert shared['reconstruction']['status'] == 'applied'
    assert shared['topology_status'] == 'model_assumed'
    assert shared['num_root_paths'] == shared['num_tips'] == 4
    assert shared['num_forks'] == 0
    _match_points(shared['tip_coords'], general['tip_coords'], tolerance=1e-7)
    assert recovered['length_px'] == pytest.approx(expected['length_px'], rel=0.05)
    for profile in profiles.values():
        # Check each root, so opposite width errors cannot cancel in the total.
        distal = profile['p'][-1]
        index = np.argmin([np.linalg.norm(distal-np.asarray(end)[::-1])
                          for _, end, _ in segments])
        dl = np.diff(profile['arc'])
        diameter = np.dot((profile['estimate'][:-1]+profile['estimate'][1:])/2,dl)/dl.sum()
        assert diameter == pytest.approx(diameters[index],rel=.08)
    for field, tolerance in [('diameter_px', 0.07), ('volume_px3', 0.15)]:
        assert recovered[field] == pytest.approx(expected[field], rel=tolerance), field
        assert abs(recovered[field] / expected[field] - 1) < abs(
            original[field] / expected[field] - 1
        ), field


def test_general_is_default_and_preserves_a_true_lateral():
    segments = [
        ((180, 30), (180, 390), 7.0),
        ((180, 170), (300, 280), 5.0),
    ]
    mask = render(segments, size=(360, 440))
    expected = truth(segments)

    default = analyze_topology(mask, binary=mask)
    explicit = analyze_topology(mask, binary=mask, root_model='general')

    for graph in (default, explicit):
        assert graph['topology_status'] == 'ok'
        assert graph['num_tips'] == 2
        assert graph['num_forks'] == 1
        assert graph['root_length_px'] == pytest.approx(expected['length_px'], rel=0.03)
        _match_points(graph['tip_coords'], [(390, 180), (280, 300)], tolerance=3.0)
    _match_points(default['tip_coords'], explicit['tip_coords'], tolerance=1e-7)


@pytest.mark.parametrize('case', ['multiple_components', 'cycle', 'no_root_direction'])
def test_shared_crown_rejects_inputs_without_a_single_rooted_tree(case):
    direction = 'top'
    if case == 'multiple_components':
        segments = [((70, 35), (70, 230), 7.0), ((190, 35), (190, 230), 7.0)]
    elif case == 'cycle':
        corners = [(65, 65), (195, 65), (195, 195), (65, 195), (65, 65)]
        segments = [(a, b, 7.0) for a, b in zip(corners[:-1], corners[1:])]
    else:
        segments = [((130, 35), (130, 230), 7.0)]
        direction = 'none'
    mask = render(segments, size=(260, 270))

    original = analyze_topology(mask, binary=mask, root_direction=direction)
    rejected = analyze_topology(
        mask, binary=mask, root_direction=direction, root_model='shared_crown'
    )

    assert rejected['reconstruction']['status'] == 'rejected'
    assert rejected['root_length_px'] == pytest.approx(original['root_length_px'], rel=1e-8)
    assert rejected['projected_length_px'] == pytest.approx(original['root_length_px'], rel=1e-8)
    assert rejected['num_tips'] == original['num_tips']
    assert rejected['num_forks'] == original['num_forks']
    assert rejected['cycle_rank'] == original['cycle_rank']
    assert rejected['strahler']['Num_Components'] == original['strahler']['Num_Components']
    if case == 'multiple_components':
        assert rejected['strahler']['Num_Components'] == 2
    elif case == 'cycle':
        assert rejected['cycle_rank'] > 0
