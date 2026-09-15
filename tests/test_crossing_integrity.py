"""Small ground-truth graphs for crossing and automatic crown integrity."""

import numpy as np

from root_topology import (
    Edge,
    adjacency,
    analyze_topology,
    resolve_crossings,
    tree_metrics,
)


def _graph(points, links):
    coords = {node: np.asarray(point, dtype=float) for node, point in enumerate(points)}
    edges = {}
    for edge_id, (u, v) in enumerate(links):
        samples = int(np.max(np.abs(coords[v] - coords[u]))) + 1
        edges[edge_id] = Edge(u, v, np.linspace(coords[u], coords[v], samples))
    return edges, coords


def test_protected_four_arm_crown_is_not_removed_as_crossing():
    edges, coords = _graph(
        [(40, 40), (20, 40), (60, 40), (40, 20), (40, 60)],
        [(0, 1), (0, 2), (0, 3), (0, 4)],
    )

    events = resolve_crossings(edges, coords, np.ones((100, 100)), protected=(0,))

    assert events == []
    assert len(adjacency(edges)[0]) == 4
    assert {(edge.u, edge.v) for edge in edges.values()} == {
        (0, 1), (0, 2), (0, 3), (0, 4)
    }


def test_adjacent_true_forks_do_not_disconnect_a_complete_root():
    # All four outer arms have perfect opposite partners, but this is a tree.
    edges, coords = _graph(
        [(30, 30), (30, 34), (30, 10), (10, 30), (30, 54), (50, 34)],
        [(0, 1), (0, 2), (0, 3), (1, 4), (1, 5)],
    )

    events = resolve_crossings(
        edges, coords, np.ones((100, 100)), preserve_components=True
    )

    stats, _, parent, cycle_rank = tree_metrics(edges, coords, base_node=2)
    assert events == []
    assert stats['Num_Components'] == 1
    assert cycle_rank == 0
    assert len(parent) == 6
    assert sum(len(ids) == 3 for ids in adjacency(edges).values()) == 2


def test_automatic_crown_preserves_a_short_true_lateral():
    # A four-pixel proximal stem and a five-pixel lateral fit the inferred box.
    mask = np.zeros((64, 64), dtype=bool)
    mask[10:41, 40] = True
    mask[[14, 14, 15, 15, 16, 16], [40, 41, 42, 43, 44, 45]] = True

    result = analyze_topology(mask, binary=mask, root_direction='top')

    assert result['topology_status'] == 'ok'
    assert result['num_tips'] == 2
    assert result['num_forks'] == 1
    assert any(np.linalg.norm(np.asarray(tip) - (16, 45)) < 2
               for tip in result['tip_coords'])
