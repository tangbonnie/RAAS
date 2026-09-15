"""Auditable cleanup of unresolved pixel holes near overlapping root bundles.

This is not an inference of biological connectivity. In particular, choosing
four-connected background can merge a diagonal one-pixel gap between roots.
The default protects those gaps; all altered pixels are returned for review.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import distance_transform_edt, find_objects, label


def repair_microholes(binary, *, max_area=4, max_inradius=1., background_connectivity=8):
    """Return ``(repaired_mask, diagnostics)`` without changing the input.

    Only bounded background components below BOTH size limits are candidates.
    Exterior background, long slits, and wider enclosed gaps are retained.
    ``background_connectivity=4`` is an explicit alternative for subpixel-gap
    merging; use its diagnostic flag in any report instead of calling it a
    lossless repair. There is no image-only proof that a tiny hole is an artifact.
    """
    mask = np.asarray(binary, dtype=bool)
    if mask.ndim != 2:
        raise ValueError('binary must be two-dimensional')
    if int(max_area) != max_area or max_area < 0:
        raise ValueError('max_area must be a nonnegative integer')
    if not np.isfinite(max_inradius) or max_inradius < 0:
        raise ValueError('max_inradius must be finite and nonnegative')
    if background_connectivity not in (4, 8):
        raise ValueError('background_connectivity must be 4 or 8')
    structure = np.ones((3, 3), dtype=bool) if background_connectivity == 8 else None
    components, _ = label(~mask, structure)
    sizes = np.bincount(components.ravel())
    border = np.unique(np.r_[components[0], components[-1],
                             components[:, 0], components[:, -1]]) if mask.size else []
    candidates = (sizes <= max_area) & (sizes > 0)
    candidates[0] = False
    candidates[border] = False
    repaired = mask.copy()
    records = []
    for ident, bounds in enumerate(find_objects(components), 1):
        if not candidates[ident]:
            continue
        local = components[bounds] == ident
        # Padding is necessary for a component that fills its bounding box.
        inradius = float(distance_transform_edt(np.pad(local, 1)).max())
        if inradius > max_inradius:
            continue
        pixels = np.argwhere(local) + [bounds[0].start, bounds[1].start]
        repaired[tuple(pixels.T)] = True
        records.append(dict(area=int(sizes[ident]), inradius_px=inradius,
                            centroid_rc=pixels.mean(axis=0).tolist(),
                            pixels_rc=pixels.tolist()))
    diagnostics = dict(
        max_area_px=int(max_area), max_inradius_px=float(max_inradius),
        background_connectivity=background_connectivity,
        subpixel_gap_merging_assumed=background_connectivity == 4,
        repaired_holes=len(records), repaired_pixels=sum(r['area'] for r in records),
        repairs=records,
    )
    return repaired, diagnostics


def bundle_contact_candidates(edges, coords, radius, base_node, *, max_separation_deg=30.):
    """Locate narrow-angle splits with a broader incoming foreground bundle.

    The output is a review aid, never a replacement for forks or a permission
    to collapse the crown. A true acute biological branch can satisfy this
    geometry too. Do not duplicate shared root lengths using this evidence alone.
    Requires a connected, acyclic graph rooted at an explicitly supplied base.
    """
    from root_topology import adjacency, angle, direction

    adj = adjacency(edges)
    if base_node not in adj or len(edges) != len(adj)-1:
        return []
    parent = {base_node: None}
    order = [base_node]
    incoming = {}
    for node in order:
        for ident in adj[node]:
            other = edges[ident].other(node)
            if other == parent[node]:
                continue
            if other in parent:
                return []
            parent[other] = node
            incoming[other] = ident
            order.append(other)
    if len(parent) != len(adj):
        return []
    candidates = []
    for node in order[1:]:
        exits = [i for i in adj[node] if i != incoming[node]]
        if len(exits) < 2:
            continue
        paths = [edges[i].away(node) for i in [incoming[node], *exits]]
        widths, directions = [], []
        for path in paths:
            sample = path[min(12, len(path)-1):min(50, len(path))].astype(int)
            widths.append(float(2*np.median(radius[tuple(sample.T)])))
            directions.append(direction(path, reach=max(15., 3*widths[-1])))
        separation = max(angle(a, b) for i, a in enumerate(directions[1:])
                         for b in directions[i+2:])
        # Demand some image support for multiple roots occupying the trunk.
        ratio = widths[0] / max(max(widths[1:]), 1e-9)
        if separation <= max_separation_deg and ratio >= 1.15:
            candidates.append(dict(node=node, rc=np.asarray(coords[node]).tolist(),
                                   separation_deg=separation, incoming_width_px=widths[0],
                                   outgoing_widths_px=widths[1:],
                                   interpretation='bundle_or_acute_branch'))
    return candidates


def trace_shared_crown(edges, coords, base_node):
    """Trace independent roots under an EXPLICIT unbranched common-crown model.

    Connectivity alone cannot distinguish a bundle splitting from a real
    lateral root. Callers must select this model; it is never an angle-based
    automatic override. Shared image segments remain in every descendant root
    and are marked inferred. The observed graph is not mutated or discarded.
    """
    from collections import Counter
    from root_topology import Edge, adjacency

    diagnostic = dict(status='rejected', model='shared_crown',
                      assumption='independent_unbranched_roots_from_common_base',
                      reason='', root_paths=[], contacts=[])
    adj = adjacency(edges)
    if base_node not in adj:
        diagnostic['reason'] = 'A root base is required.'
        return None, diagnostic
    parent = {base_node: None}
    incoming = {}
    order = [base_node]
    for node in order:
        for ident in adj[node]:
            if ident == incoming.get(node):
                continue
            other = edges[ident].other(node)
            if other in parent:
                diagnostic['reason'] = 'Cycles or parallel contacts remain unresolved.'
                return None, diagnostic
            parent[other] = node
            incoming[other] = ident
            order.append(other)
    if len(parent) != len(adj):
        diagnostic['reason'] = 'Disconnected fragments require review before tracing.'
        return None, diagnostic
    tips = sorted((n for n in adj if len(adj[n]) == 1 and n != base_node),
                  key=lambda n: tuple(coords[n]))
    if len(tips) < 2:
        diagnostic['reason'] = 'At least two visible distal paths are required.'
        return None, diagnostic
    routes = []
    for tip in tips:
        chain = []
        node = tip
        while node != base_node:
            chain.append((incoming[node], parent[node]))
            node = parent[node]
        routes.append(chain[::-1])
    multiplicity = Counter(ident for chain in routes for ident, _ in chain)
    traced = {}
    for root_id, (tip, chain) in enumerate(zip(tips, routes), 1):
        parts, flags = [], []
        for index, (ident, upstream) in enumerate(chain):
            path = edges[ident].away(upstream)
            start = 0 if index == 0 else 1
            parts.append(path[start:])
            flags.append(np.full(len(path)-start, multiplicity[ident] > 1, bool))
        path, inferred = np.vstack(parts), np.concatenate(flags)
        edge = Edge(base_node, tip, path, inferred_mask=inferred)
        traced[root_id] = edge
        dl = np.linalg.norm(np.diff(path, axis=0), axis=1)
        dl *= edge.length / max(dl.sum(), 1e-9)
        # A segment meeting a shared sample is also uncertain at the join.
        shared_length = float(dl[inferred[:-1] | inferred[1:]].sum())
        diagnostic['root_paths'].append(dict(
            root_id=f'R{root_id}', tip_rc=coords[tip].tolist(),
            length_px=edge.length, inferred_length_px=shared_length,
            observed_edge_ids=[int(ident) for ident, _ in chain]))
    for node in order:
        if node == base_node or len(adj[node]) < 3:
            continue
        diagnostic['contacts'].append(dict(
            rc=coords[node].tolist(),
            incoming_root_count=multiplicity[incoming[node]],
            outgoing_root_counts=[multiplicity[i] for i in adj[node] if i != incoming[node]],
            interpretation='bundle_separation_under_selected_model'))
    projected = float(sum(e.length for e in edges.values()))
    expanded = float(sum(e.length for e in traced.values()))
    inferred_length = sum(r['inferred_length_px'] for r in diagnostic['root_paths'])
    diagnostic.update(status='applied', projected_length_px=projected,
                      traced_length_px=expanded,
                      overlap_added_length_px=expanded-projected,
                      inferred_path_length_px=inferred_length,
                      path_inferred_length_fraction=inferred_length/expanded,
                      width_assumption='exclusive_segment_extrapolation')
    return traced, diagnostic
