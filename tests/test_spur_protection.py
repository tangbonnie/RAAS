"""Short laterals have external silhouettes; interior cap branches do not."""
import numpy as np
import pytest
from skimage.morphology import skeletonize

from root_topology import analyze_topology


@pytest.mark.parametrize('turns,direction', [(0, 'top'), (1, 'left'),
                                           (2, 'bottom'), (3, 'right')])
def test_short_thin_lateral_beside_thick_parent_survives(turns, direction):
    mask = np.zeros((240, 240), dtype=bool)
    mask[20:220, 90:130] = True
    # A three-pixel lateral projects ten pixels beyond a 40-pixel parent.
    # Its medial path is shorter than the old 1.5-parent-radius cutoff.
    mask[110:113, 129:140] = True
    endpoint = np.array([111., 138.])
    for _ in range(turns):
        endpoint = np.array([239. - endpoint[1], endpoint[0]])
    mask = np.rot90(mask, turns)
    result = analyze_topology(skeletonize(mask), binary=mask,
                              root_direction=direction, crossing_context=False)
    assert result['num_tips'] == 2
    assert result['num_forks'] == 1
    assert np.min(np.linalg.norm(np.asarray(result['tip_coords']) - endpoint,
                                 axis=1)) <= 3


def test_short_interior_raster_branch_is_still_pruned():
    mask = np.zeros((240, 240), dtype=bool)
    mask[20:220, 90:130] = True
    skeleton = np.zeros_like(mask)
    skeleton[40:200, 109] = True
    skeleton[111, 109:123] = True
    # This side arm lies entirely within the parent inscribed disk and does
    # not correspond to any lateral projection of the foreground silhouette.
    result = analyze_topology(skeleton, binary=mask, crossing_context=False)
    assert result['num_tips'] == 1
    assert result['num_forks'] == 0
    assert result['raster_pruned'] == 1
