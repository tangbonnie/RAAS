import numpy as np
from PIL import Image,ImageDraw
from root_topology import Edge,analyze_topology,resolve_crossings,adjacency

def test_three_roots_cross_at_one_location():
    im=Image.new('L',(300,300));draw=ImageDraw.Draw(im)
    for theta in (0,60,120):
        v=110*np.array([np.cos(np.deg2rad(theta)),np.sin(np.deg2rad(theta))])
        draw.line([tuple(150-v),tuple(150+v)],fill=255,width=5)
    mask=np.asarray(im)>0
    g=analyze_topology(mask,binary=mask,root_direction='none')
    assert (g['num_tips'],g['num_forks'],g['num_crossings'])==(6,0,1)

def test_isolated_noise_above_root_cannot_become_root_base():
    mask=np.zeros((150,150),bool)
    mask[3:8,8]=True;mask[40:140,75:78]=True
    g=analyze_topology(mask,binary=mask)
    assert len(g['base_coords'])==1
    assert g['base_coords'][0][0]>30
    assert len(g['fragment_tip_coords'])==2

def test_short_jagged_arm_uses_continuation_past_nearby_lateral():
    coords={i:np.array(p,float) for i,p in enumerate([(50,50),(50,56),(50,90),(70,60),(50,10),(10,50),(90,50)])}
    edges={i:Edge(a,b,np.linspace(coords[a],coords[b],31)) for i,(a,b) in enumerate([(0,1),(1,2),(1,3),(0,4),(0,5),(0,6)])}
    edges[0]=Edge(0,1,np.array([(50,50),(52,53),(50,56)],float))
    radius=np.ones((100,100))*2
    before=dict(edges)
    assert resolve_crossings(before,dict(coords),radius,allow_short_context=False)==[]
    events=resolve_crossings(edges,coords,radius)
    assert len(events)==1
    assert 0 not in adjacency(edges)
    assert sum(len(ids)==3 for ids in adjacency(edges).values())==1
