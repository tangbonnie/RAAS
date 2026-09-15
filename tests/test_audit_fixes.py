"""Regression cases for the supplied audit; no full benchmark rerun."""
from pathlib import Path
import uuid
import json
import numpy as np
import pytest
from PIL import Image, ImageDraw, PngImagePlugin
from skimage.morphology import skeletonize
from root_analysis import analyze_root_image, _analysis_worker_task, compute_multifractal_spectrum
from preprocess import _preprocess_worker_task
from calibration import image_scale

@pytest.fixture
def sample():
    parent=Path(__file__).resolve().parents[1]/'build'
    parent.mkdir(exist_ok=True)
    folder=parent/'audit-inputs'/uuid.uuid4().hex
    folder.mkdir(parents=True)
    im=Image.new('L',(120,120));pen=ImageDraw.Draw(im)
    pen.line([(60,5),(60,110)],fill=255,width=3)
    pen.line([(60,45),(105,90)],fill=255,width=3)
    b=folder/'binary.png';s=folder/'skeleton.png'
    im.save(b)
    Image.fromarray(skeletonize(np.asarray(im)>0).astype('uint8')*255).save(s)
    yield folder,b,s

@pytest.mark.parametrize('box',[[200,200,220,220],[70,70,20,20],[0,0,1],[float('nan'),0,10,10]])
def test_bad_crown_is_diagnostic_not_batch_exception(sample,box):
    _,b,s=sample
    r=analyze_root_image(b,s,crown_box=box)
    assert r['Topology_Status']=='invalid_crown'
    assert r['Topology_Error']
    assert np.isnan(r['Topological_Index'])
    assert np.isnan(r['Avg_Branch_Angle_deg'])
    assert r['Root_Length_px']>0

def test_malformed_review_is_reported_and_explicit_override_wins(sample):
    _,b,s=sample
    Path(str(b)+'.review.json').write_text('{broken')
    assert analyze_root_image(b,s)['Topology_Status']=='invalid_crown'
    assert analyze_root_image(b,s,crown_box=[0,50,12,70])['Topology_Status']=='ok'

def test_analysis_worker_preserves_explicit_base_and_crown(sample):
    _,b,s=sample
    args=(str(b),str(s),None,'test','top',(110,60),[0,50,12,70])
    got=_analysis_worker_task(args)
    direct=analyze_root_image(b,s,base_rc=args[5],crown_box=args[6])
    assert got['Crown_Annotation']=='manual_rectangle'
    for key in ['Num_Tips','Num_Forks','Topological_Index','Root_Length_px']:
        assert got[key]==direct[key]
    base_only=_analysis_worker_task(args[:6])
    assert np.allclose(base_only['_base_coords'],analyze_root_image(b,s,base_rc=args[5])['_base_coords'])

@pytest.mark.parametrize('extra',[(),('dark',),('dark',600)])
def test_preprocess_worker_legacy_and_dpi_override(sample,extra):
    folder,b,_=sample
    # A true dark-on-white line drawing, independent of analysis mask.
    im=Image.open(b).convert('L'); im=Image.fromarray(255-np.asarray(im));src=folder/'source.png';im.save(src)
    out=folder/'processed'
    args=(str(src),str(out),'line_art',15,51,0.0,1,0,0,1.01,0,0)+extra
    _preprocess_worker_task(args)
    dpi,origin=image_scale(out/'binary/source.png')
    if len(extra)==2:
        assert dpi==pytest.approx(600,abs=.02) and origin=='user_supplied'
    else:
        assert dpi is None and origin=='unknown'

def test_unknown_provenance_cannot_be_overruled_by_stale_metadata(sample):
    folder,_,_=sample
    p=folder/'scale.png';meta=PngImagePlugin.PngInfo();meta.add_text('Scale_Source','unknown')
    Image.new('L',(10,10)).save(p,dpi=(600,600),pnginfo=meta)
    assert image_scale(p)==(None,'unknown')
    assert image_scale(p,300)==(300,'user_supplied')

def test_unstable_spectrum_has_no_usable_derived_scalars():
    y,x=np.mgrid[:128,:128];im=(x-64)**2+(y-64)**2<45**2
    r=compute_multifractal_spectrum(im)
    assert r['quality']=='finite_scale_unstable'
    assert all(np.isnan(r[k]) for k in ['Delta_alpha','Delta_f','alpha_0','f_alpha_0'])
    assert all(np.isfinite(r[k]) for k in ['D0','D1','D2'])

@pytest.mark.parametrize('num',[5,9,41])
def test_uniform_aligned_boxes_are_monofractal_independent_of_q_step(num):
    r=compute_multifractal_spectrum(np.ones((256,256),bool),q_range=(0,2),q_num=num,min_box=16,num_sizes=3)
    assert r['quality']=='fit_consistent'
    assert r['Delta_alpha']==pytest.approx(0,abs=1e-4)
    assert r['alpha_0']==pytest.approx(2,abs=1e-4)
