import numpy as np
import pytest
from tests.accuracy_phantoms import render,truth,cross,plant
from root_topology import Edge,analyze_topology,measure_paths

@pytest.mark.parametrize('theta,width,scale',[(15,9,1),(30,9,1),(60,9,1),(90,9,1),(22.5,9,1),(45,17,1),(80,17,1),(22.5,9,2),(45,17,2),(80,17,2)])
def test_overlapping_roots_against_continuous_cylinder_truth(theta,width,scale):
    segments=cross(theta,width);mask=render(segments,scale=scale)
    graph=analyze_topology(mask,binary=mask,root_direction='none')
    measured=measure_paths(graph['_resolved_edges'],mask);expected=truth(segments)
    assert graph['num_crossings']==1
    assert measured['length_px']/scale==pytest.approx(expected['length_px'],rel=.025)
    assert measured['diameter_px']/scale==pytest.approx(expected['diameter_px'],rel=.05)
    assert measured['volume_px3']/scale**3==pytest.approx(expected['volume_px3'],rel=.10)
    assert measured['diameter_measured_fraction']>0.4
    assert measured['diameter_unresolved_fraction']==0

def test_thin_root_crossing_thick_root_does_not_inherit_its_diameter():
    segments=cross(25,17);segments[1]=(segments[1][0],segments[1][1],9)
    mask=render(segments);graph=analyze_topology(mask,binary=mask,root_direction='none')
    measured=measure_paths(graph['_resolved_edges'],mask);expected=truth(segments)
    assert measured['diameter_px']==pytest.approx(expected['diameter_px'],rel=.05)
    assert measured['volume_px3']==pytest.approx(expected['volume_px3'],rel=.10)

@pytest.mark.parametrize('turn',[0,1,2,3])
def test_fan_crown_is_not_an_extra_lateral_branch(turn):
    mask=np.rot90(render(plant(2)),turn)
    graph=analyze_topology(mask,binary=mask,root_direction=['top','left','bottom','right'][turn])
    assert (graph['num_tips'],graph['num_forks'],graph['num_crossings'])==(9,6,3)
    assert graph['topology_status']=='ok'

def test_true_three_way_branch_below_a_stem_is_not_a_crown():
    segments=[((350,55),(350,70),5)]+[((350,70),end,5) for end in [(150,450),(350,480),(550,450)]]
    mask=render(segments);graph=analyze_topology(mask,binary=mask)
    assert (graph['num_tips'],graph['num_forks'])==(3,1)
    assert graph['crown_source']=='none'

def test_self_crossing_width_is_independent_of_graph_segmentation():
    segments=[((40,40),(200,200),20),((200,200),(40,200),20),((40,200),(200,40),20)]
    mask=render(segments,size=(260,260))
    paths=[np.linspace(np.asarray(a)[::-1],np.asarray(b)[::-1],int(np.linalg.norm(np.asarray(a)-b))+1) for a,b,w in segments]
    joined={0:Edge(0,3,np.vstack([paths[0],paths[1][1:],paths[2][1:]]))}
    split={i:Edge(i,i+1,p) for i,p in enumerate(paths)}
    a,b=measure_paths(joined,mask),measure_paths(split,mask)
    for m in (a,b):
        assert m['diameter_px']==pytest.approx(20,rel=.03)
        assert m['volume_px3']/m['length_px']==pytest.approx(np.pi*100,rel=.06)
    assert a['volume_px3']/a['length_px']==pytest.approx(b['volume_px3']/b['length_px'],rel=.02)

def test_tapered_root_preserves_local_diameter_variation():
    y,x=np.mgrid[:800,:800]
    diameter=5+12*(y-100)/600
    mask=(y>=100)&(y<700)&(np.abs(x-350)<diameter/2)
    graph=analyze_topology(mask,binary=mask)
    measured=measure_paths(graph['_resolved_edges'],mask)
    # Frustum volume: pi * L / 12 * (d0² + d0*d1 + d1²).
    assert measured['length_px']==pytest.approx(600,rel=.01)
    assert measured['diameter_px']==pytest.approx(11,rel=.01)
    assert measured['volume_px3']==pytest.approx(np.pi*600/12*(25+85+289),rel=.02)
