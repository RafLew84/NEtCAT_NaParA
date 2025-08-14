import numpy as np
from skimage.morphology import rectangle, erosion, dilation, reconstruction
from skimage.measure import regionprops, label
from skimage.transform import rotate
from skimage.filters import threshold_otsu

def _directional_morph_reconstruction(img, length_px=31, width_px=1, angle_deg=0.0,
                                      mode="open", protect_min_area_px=0,
                                      protect_min_minor_px=0):
    selem = rectangle(width_px, length_px)
    selem_rot = rotate(selem.astype(float), angle=angle_deg, resize=True) > 0.5
    if mode == "open":
        eroded = erosion(img, selem_rot)
        opened = reconstruction(eroded, img)
        mask = img - opened
    elif mode == "close":
        dilated = dilation(img, selem_rot)
        closed = reconstruction(dilated, img, method='erosion')
        mask = closed - img
    else:
        raise ValueError("mode must be 'open' or 'close'")

    if protect_min_area_px > 0 or protect_min_minor_px > 0:
        lbl = label(mask > threshold_otsu(mask))
        props = regionprops(lbl)
        for p in props:
            if p.area >= protect_min_area_px and p.minor_axis_length >= protect_min_minor_px:
                mask[lbl == p.label] = 0
    return img - mask
