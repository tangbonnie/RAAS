import numpy as np
import pytest

from root_segmentation import segment_root_intensity


def test_dim_one_pixel_lateral_and_gaps_are_preserved():
    image = np.zeros((80, 80), np.float32)
    image[5:75, 38:42] = 1
    image[25, 10:39] = .25
    image[27, 10:39] = .25
    image[2, 2] = .03
    mask, info = segment_root_intensity(image)
    assert mask[25, 10:39].all()
    assert mask[27, 10:39].all()
    assert not mask[26, 10:38].any()
    assert not mask[2, 2]
    assert info["foreground"] == "light"


def test_touching_boundary_root_is_not_eroded():
    image = np.zeros((50, 60), np.uint8)
    image[:, 29:32] = 255
    mask, info = segment_root_intensity(image)
    assert np.array_equal(mask, image > 0)
    assert info["border_foreground_pixels"] == 6


def test_polarity_inversion_and_holes_preserved():
    image = np.zeros((80, 80), np.float32)
    image[10:70, 35:45] = 1
    image[30:40, 39:41] = 0
    a, _ = segment_root_intensity(image)
    b, _ = segment_root_intensity(1 - image)
    assert np.array_equal(a, b)
    assert not a[30:40, 39:41].any()


@pytest.mark.parametrize("value", [0.0, 1.0])
def test_uniform_image_is_empty(value):
    mask, _ = segment_root_intensity(np.full((20, 20), value))
    assert not mask.any()
