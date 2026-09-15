"""Opt-in repair of photographic pores inside a broad proximal cut stem.

The assumption is explicit: several enclosed dark regions inside a stable,
broad cut-stem silhouette are photographic voids, not anatomical openings.
Exterior-connected gaps are never closed. This is a segmentation operation;
the returned repaired mask must be skeletonized again before quantification.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage


def _oriented(array, direction):
    if direction == 'bottom':
        return array[::-1]
    if direction == 'left':
        return array.T
    if direction == 'right':
        return array.T[::-1]
    return array


def repair_proximal_stem(binary, root_direction='top', enabled=False):
    """Return ``(repaired_mask, diagnostics, inferred_pixel_mask)``.

    Disabled by default. Enabled mode proposes a conservative terminal-stem
    region from the largest foreground component. It requires a broad,
    approximately parallel-sided cut end, at least three enclosed pores, and
    a substantial downstream structure. It stops at the first silhouette
    expansion, appreciable bend, or low-density cross section. Thin roots,
    pointed fan crowns, single loops, and exterior-connected slots are not
    healed. Rotation is controlled by the supplied proximal root direction.

    All coordinates in ``roi_rc`` are original-image, half-open bounds
    ``[row_start, col_start, row_stop, col_stop]``. Every changed pixel is
    returned explicitly; this is a model-based repair, never observed tissue.
    No original foreground pixel is removed.
    """
    mask = np.asarray(binary, dtype=bool)
    if mask.ndim != 2 or not mask.size:
        raise ValueError('expected a nonempty two-dimensional binary image')
    if root_direction not in ('top', 'bottom', 'left', 'right', 'none'):
        raise ValueError('root_direction must be top/bottom/left/right/none')
    repaired = mask.copy()
    inferred = np.zeros_like(mask)
    info = dict(enabled=bool(enabled), status='disabled', root_direction=root_direction,
                assumption='enclosed_proximal_stem_voids_are_photographic',
                method='enclosed_holes_in_stable_cut_stem_v1', roi_rc=None,
                added_pixels=0, filled_holes=0, added_fraction=0.0,
                uncertainty='inferred_silhouette', background_connectivity=8)

    def reject(reason):
        info.update(status='not_applied', reason=reason)
        return repaired, info, inferred

    if not enabled:
        return repaired, info, inferred
    if root_direction == 'none':
        return reject('proximal_direction_required')
    oriented = _oriented(mask, root_direction)
    labels, count = ndimage.label(oriented, structure=np.ones((3, 3), bool))
    if not count:
        return reject('empty_foreground')
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    primary_label = int(sizes.argmax())
    region = ndimage.find_objects(labels, max_label=primary_label)[primary_label - 1]
    r0, r1 = region[0].start, region[0].stop
    c0, c1 = region[1].start, region[1].stop
    depth = r1 - r0
    primary = labels[region] == primary_label
    widths = primary.shape[1] - np.argmax(primary[:, ::-1], axis=1) - np.argmax(primary, axis=1)
    left = np.argmax(primary, axis=1) + c0
    right = left + widths
    occupancy = primary.sum(axis=1) / np.maximum(1, widths)
    probe = min(depth, max(8, int(round(.025 * depth))))
    width = float(np.median(widths[:probe]))
    info['stem_width_px'] = width
    if width < max(16., .012 * depth) or depth < 4 * width:
        return reject('no_broad_terminal_stem')
    ramp = max(1, int(np.ceil(.2 * width)))
    stable_end = int(np.ceil(.7 * width))
    if stable_end >= depth:
        return reject('terminal_stem_too_short')
    stable = slice(ramp, stable_end)
    center = (left + right - 1) * .5
    reference_center = float(np.median(center[stable]))
    stable_rows = ((widths[stable] >= .8 * width) &
                   (widths[stable] <= 1.2 * width) &
                   (occupancy[stable] >= .6) &
                   (np.abs(center[stable] - reference_center) <= .12 * width))
    # A pointed apex gradually widening into a fan must not qualify as a cut end.
    if float(np.mean(stable_rows)) < .95 or np.median(widths[:ramp]) < .6 * width:
        return reject('no_stable_cut_end')
    end = min(depth, int(np.ceil(2 * width)))
    for row in range(stable_end, end):
        if (widths[row] < .8 * width or widths[row] > 1.2 * width or
                occupancy[row] < .55 or
                abs(center[row] - reference_center) > .12 * width):
            end = row
            break
    # A hole touching this boundary stays open to the exterior in the local
    # flood fill. Consequently a gap crossing the candidate ROI is not bridged.
    lo = int(left[:end].min())
    hi = int(right[:end].max())
    local = oriented[r0:r0 + end, lo:hi]
    holes = ndimage.binary_fill_holes(local, structure=np.ones((3, 3), bool)) & ~local
    hole_labels, n_holes = ndimage.label(holes, structure=np.ones((3, 3), bool))
    areas = np.bincount(hole_labels.ravel(), minlength=n_holes + 1)
    substantive = areas[1:] >= max(2., .0005 * width * width)
    if int(substantive.sum()) < 3:
        return reject('insufficient_enclosed_pore_evidence')
    if holes.sum() > .35 * local.size:
        return reject('large_void_ambiguous')
    # Reject a large genuine lumen/loop even if smaller raster holes accompany
    # it. The envelope cannot establish that such a large opening is tissue.
    hole_radius = ndimage.distance_transform_edt(holes)
    if float(hole_radius.max()) > .2 * width:
        return reject('large_void_ambiguous')
    _oriented(inferred, root_direction)[r0:r0 + end, lo:hi] = holes
    repaired |= inferred
    roi_mask = np.zeros_like(mask)
    _oriented(roi_mask, root_direction)[r0:r0 + end, lo:hi] = True
    yy, xx = np.nonzero(roi_mask)
    info.update(status='applied', reason='stable_cut_stem_with_enclosed_pores',
                roi_rc=[int(yy.min()), int(xx.min()), int(yy.max()) + 1, int(xx.max()) + 1],
                added_pixels=int(inferred.sum()), filled_holes=int(n_holes),
                added_fraction=float(inferred.sum()) / max(1, int(repaired.sum())),
                local_added_fraction=float(holes.sum()) / max(1, int(local.size)))
    return repaired, info, inferred
