"""Explicit scale provenance; filenames never establish a physical scale."""
import math
from PIL import Image


def image_scale(path, override=None):
    if override is not None:
        if not math.isfinite(float(override)) or not 10 <= float(override) <= 10000:
            raise ValueError('DPI must be between 10 and 10000')
        return float(override), 'user_supplied'
    with Image.open(path) as im:
        provenance = im.info.get('Scale_Source')
        if provenance == 'unknown':
            return None, 'unknown'
        dpi = im.info.get('dpi')
        if dpi and len(dpi) >= 2:
            x,y = map(float,dpi[:2])
            if 10 <= x <= 10000 and abs(x-y)/x < .01:
                return (x+y)/2, provenance or 'metadata'
        # TIFF/EXIF resolution units: 2=inches, 3=centimetres.
        tags = getattr(im,'tag_v2',None) or im.getexif()
        if tags and tags.get(296) in (2,3) and tags.get(282) and tags.get(283):
            x,y = float(tags[282]),float(tags[283])
            factor = 2.54 if tags[296] == 3 else 1
            if x > 0 and abs(x-y)/x < .01:
                return x*factor, provenance or 'metadata'
    return None, 'unknown'
