from pathlib import Path
import json
import numpy as np
import pytest
from PIL import Image, ImageDraw
from root_topology import analyze_topology, measure_paths, Edge
from root_analysis import analyze_root_image
from calibration import image_scale


def drawing(paths, width=5, size=(260,260)):
    im=Image.new('L',size)
    d=ImageDraw.Draw(im)
    for p in paths:
        d.line(p,fill=255,width=width)
    return np.asarray(im)>0


def test_rooted_herringbone_shares_base_and_has_order_two():
    b=drawing([[(100,20),(100,240)],[(100,60),(50,130)],
               [(100,110),(170,180)],[(100,170),(55,220)]])
    a=analyze_topology(b,binary=b)
    assert (a['num_tips'],a['num_forks'],a['num_crossings']) == (4,3,0)
    assert a['strahler']['_TI_magnitude']==4
    assert a['strahler']['_TI_altitude']==4
    assert a['strahler']['_TI']==pytest.approx(1.)
    assert a['strahler']['Strahler_Max_Order']==2
    assert a['strahler']['Strahler_Bifurcation_Ratio']==4
    assert len(a['_strahler_edge_viz'])==len(a['edges'])


def test_crossing_is_two_paths_not_biological_connection():
    b=drawing([[(100,20),(100,240)],[(100,60),(200,200)],
               [(100,130),(220,190)]],width=3)
    a=analyze_topology(b,binary=b)
    assert (a['num_tips'],a['num_forks'],a['num_crossings'])==(3,2,1)
    assert a['topology_status']=='ok'
    assert a['strahler']['Strahler_Max_Order']==2
    assert a['strahler']['_TI_magnitude']==3
    assert a['strahler']['_TI']==pytest.approx(1.)


def test_rotation_with_explicit_direction():
    b=drawing([[(100,20),(100,240)],[(100,70),(180,150)]])
    a=analyze_topology(b,binary=b)
    c=analyze_topology(np.rot90(b),binary=np.rot90(b),root_direction='left')
    assert a['num_tips']==c['num_tips']==2
    assert a['num_forks']==c['num_forks']==1
    assert a['root_length_px']==pytest.approx(c['root_length_px'],rel=.015)


def test_remaining_cycle_is_not_silently_spanning_tree():
    b=drawing([[(70,70),(190,70),(190,190),(70,190),(70,70)]])
    a=analyze_topology(b,binary=b)
    assert a['topology_status']=='unresolved'
    assert np.isnan(a['strahler']['Strahler_Max_Order'])


def test_variable_width_volume_uses_local_squared_width():
    b=np.zeros((240,140),dtype=bool)
    b[20:101,36:45]=True
    b[130:211,72:89]=True
    edges={0:Edge(0,1,np.column_stack((np.arange(25,96),np.full(71,40)))),
           1:Edge(2,3,np.column_stack((np.arange(135,206),np.full(71,80))))}
    m=measure_paths(edges,b)
    assert m['length_px']==140
    assert m['diameter_px']==pytest.approx(13,abs=.1)
    assert m['volume_px3']==pytest.approx(np.pi/4*(9**2+17**2)*70,rel=.02)


def test_dpi_changes_units_not_topology():
    b=drawing([[(100,20),(100,240)],[(100,70),(180,150)]])
    a=analyze_topology(b,binary=b,dpi=300)
    c=analyze_topology(b,binary=b,dpi=600)
    assert a['tip_coords']==c['tip_coords']
    assert a['crossing_coords']==c['crossing_coords']
    assert a['root_length_cm']==pytest.approx(c['root_length_cm']*2)


def test_missing_scale_never_invents_measured_centimetres():
    tmp_path=Path(__file__).resolve().parents[1]/'results'/'topology_audit'/'test_inputs'
    tmp_path.mkdir(parents=True,exist_ok=True)
    b=drawing([[(100,20),(100,240)]])
    p=tmp_path/'600-sample.png'
    Image.fromarray(b.astype('uint8')*255).save(p)
    assert image_scale(p)==(None,'unknown')
    a=analyze_root_image(p,p)
    assert np.isnan(a['Root_Length_cm'])
    assert np.isnan(a['Tip_Density_per_cm'])
    assert a['Root_Length_px']>200
    c=analyze_root_image(p,p,dpi=600)
    assert c['Scale_Source']=='user_supplied'
    assert c['Root_Length_cm']==pytest.approx(c['Root_Length_px']*2.54/600,abs=.0001)


@pytest.mark.parametrize('number,tips,forks,crossings',[(17,7,6,1),(33,6,5,1)])
def test_reviewed_crossing_samples(number,tips,forks,crossings):
    p=optional_copper_sample(f'600-dicot-sim-{number}-1-120-15-deg0.jpg')
    b=np.asarray(Image.open(p).convert('L'))<128
    a=analyze_topology(b,binary=b)
    assert (a['num_tips'],a['num_forks'],a['num_crossings'])==(tips,forks,crossings)
    assert a['topology_status']=='ok'


def test_empty_and_single_pixel_are_safe():
    b=np.zeros((20,20),dtype=bool)
    for single in (False,True):
        b[10,10]=single
        a=analyze_topology(b,binary=b)
        assert a['num_tips']==0
        assert a['topology_status']=='empty'


REFERENCES=json.loads((Path(__file__).parent/'root_demo_references.json').read_text(encoding='utf-8'))['samples']


def optional_copper_sample(filename):
    """Historical reference images are optional; the public release has four examples."""
    import os
    directory = os.environ.get('RAAS_EXTERNAL_COPPER_DIR')
    if not directory:
        pytest.skip('Optional reference data: set RAAS_EXTERNAL_COPPER_DIR')
    path = Path(directory) / filename
    if not path.is_file():
        pytest.skip(f'Optional reference image unavailable: {filename}')
    return path


@pytest.mark.parametrize('filename',list(REFERENCES))
def test_reviewed_demo_reference_counts(filename):
    ref=REFERENCES[filename]
    p=optional_copper_sample(filename)
    b=np.asarray(Image.open(p).convert('L'))<128
    a=analyze_topology(b,binary=b,crown_box=ref.get('crown_box'))
    assert (a['num_tips'],a['num_forks'],a['num_crossings'])==(ref['tips'],ref['forks'],ref['crossings'])
    assert a['topology_status']=='ok'
    assert a['strahler']['_TI_magnitude']==ref['tips']


@pytest.mark.parametrize('degrees',[0,30,60,90])
@pytest.mark.parametrize('width',[5,9,17])
def test_analytic_strip_geometry(degrees,width):
    # Independent continuous rectangle model rasterized at pixel centres.
    y,x=np.mgrid[:300,:300]
    v=np.array([np.sin(np.radians(degrees)),np.cos(np.radians(degrees))])
    q=np.stack((y-150,x-150),axis=-1)
    b=(abs(q@v)<=100)&(abs(q[...,0]*v[1]-q[...,1]*v[0])<=width/2)
    a=analyze_topology(b,binary=b)
    m=measure_paths(a['_resolved_edges'],b)
    assert (a['num_tips'],a['num_forks'])==(1,0)
    assert m['length_px']==pytest.approx(200,rel=.025)
    assert m['diameter_px']==pytest.approx(width,rel=.05)
    assert m['volume_px3']==pytest.approx(np.pi*width**2/4*200,rel=.085)


def test_explicit_dpi_overrides_existing_metadata():
    p=Path(__file__).resolve().parents[1]/'results'/'topology_audit'/'test_inputs'/'scale.png'
    p.parent.mkdir(parents=True,exist_ok=True)
    Image.new('L',(10,10)).save(p,dpi=(300,300))
    assert image_scale(p)[0]==pytest.approx(300,abs=.02)
    assert image_scale(p,600)==(600.,'user_supplied')
