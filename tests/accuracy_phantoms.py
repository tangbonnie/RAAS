"""Independent vector geometry used to measure raster quantification error."""
import numpy as np
from PIL import Image,ImageDraw

def render(segments,size=(800,800),scale=1):
    # Sample continuous rectangles at subpixel centres, then require >50% coverage.
    # No inclusive integer-polygon endpoint bias from a drawing library.
    ss=4;w,h=round(size[0]*scale),round(size[1]*scale)
    high=np.zeros((h*ss,w*ss),bool)
    for a,b,width in segments:
        a,b=np.array(a,float)*scale,np.array(b,float)*scale
        v=b-a;length=np.linalg.norm(v);v/=length;normal=np.array([-v[1],v[0]])
        r=width*scale/2
        lo=np.floor((np.minimum(a,b)-r+0.5)*ss).astype(int);hi=np.ceil((np.maximum(a,b)+r+0.5)*ss).astype(int)
        x0,y0=np.maximum(lo,0);x1,y1=np.minimum(hi,[w*ss,h*ss])
        yy,xx=np.mgrid[y0:y1,x0:x1];dx=(xx+.5)/ss-.5-a[0];dy=(yy+.5)/ss-.5-a[1]
        t=dx*v[0]+dy*v[1];n=dx*normal[0]+dy*normal[1]
        high[y0:y1,x0:x1]|=(t>=0)&(t<=length)&(np.abs(n)<=r)
    return high.reshape(h,ss,w,ss).mean(axis=(1,3))>.5

def truth(segments):
    lengths=np.array([np.linalg.norm(np.array(b)-a) for a,b,w in segments]);widths=np.array([w for a,b,w in segments])
    return dict(length_px=lengths.sum(),diameter_px=np.dot(lengths,widths)/lengths.sum(),surface_px2=np.dot(lengths,np.pi*widths),volume_px3=np.dot(lengths,np.pi*widths**2/4))

def cross(theta,width=9):
    center=np.array([350.,350.]);v=200*np.array([np.cos(np.deg2rad(theta)),np.sin(np.deg2rad(theta))])
    return [((150,350),(550,350),width),(center-v,center+v,width)]

def plant(laterals=3):
    origin=np.array([350.,30.]);ends=[np.array([80.,610.]),np.array([350.,745.]),np.array([670.,620.])]
    segs=[]
    for j,end in enumerate(ends):
        segs.append((origin,end,7.))
        for k,f in enumerate(np.linspace(.20,.80,laterals)):
            attach=origin+(end-origin)*f
            side=-1 if (k+j)%2 else 1
            delta=np.array([side*(120+15*j),110-9*k])
            segs.append((attach,attach+delta,3.5))
    return segs

def crossings(segments):
    count=0
    for i,(a,b,_) in enumerate(segments):
        a,b=np.array(a),np.array(b)
        for c,d,_ in segments[i+1:]:
            c,d=np.array(c),np.array(d);matrix=np.column_stack((b-a,c-d))
            if abs(np.linalg.det(matrix))<1e-9:continue
            t,u=np.linalg.solve(matrix,c-a)
            if 1e-6<t<1-1e-6 and 1e-6<u<1-1e-6:count+=1
    return count
