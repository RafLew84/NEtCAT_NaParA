import numpy as np
from skimage.morphology import rectangle, erosion, dilation, reconstruction
from skimage.measure import regionprops, label
from skimage.transform import rotate
from skimage.filters import threshold_otsu

def _directional_morph_reconstruction(img, length_px=31, width_px=1, angle_deg=0.0,
                                      mode="open", protect_min_area_px=0,
                                      protect_min_minor_px=0):
    im = img.astype(np.float32, copy=False)
    L = max(3, int(length_px) | 1); W = max(1, int(width_px))
    se = rectangle(W, L)
    rot = rotate(im, -angle_deg, resize=False, preserve_range=True, order=1, mode="edge")
    if mode == "open":
        seed = erosion(rot, se); rec = reconstruction(seed, rot, method='dilation')
        removed = rot - rec
    elif mode == "close":
        seed = dilation(rot, se); rec = reconstruction(seed, rot, method='erosion')
        removed = rec - rot
    else:
        return img
    # ochrona
    if protect_min_area_px > 0 or protect_min_minor_px > 0:
        pos = removed > 0
        vals = removed[pos]
        thr = threshold_otsu(vals.astype(np.float32)) if vals.size >= 64 else (float(vals.mean()) if vals.size else 0.0)
        cand = np.zeros_like(pos, bool); cand[pos] = removed[pos] > max(thr, 0.0)
        lab = label(cand, connectivity=2)
        if lab.max() > 0:
            restore = np.zeros_like(cand, bool)
            for r in regionprops(lab):
                if (protect_min_area_px and r.area >= protect_min_area_px) or \
                   (protect_min_minor_px and getattr(r, "minor_axis_length", 0.0) >= protect_min_minor_px):
                    restore[lab == r.label] = True
            rec[restore] = rot[restore]
    out = rotate(rec, angle_deg, resize=False, preserve_range=True, order=1, mode="edge")
    return out.astype(np.float32, copy=False)
