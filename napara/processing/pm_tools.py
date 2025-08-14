import numpy as np

def anisotropic_diffusion_pm(img, n_iter=10, kappa=20, gamma=0.15, option=1):
    img = img.astype(np.float32)
    for _ in range(n_iter):
        nablaN = np.roll(img, -1, axis=0) - img
        nablaS = np.roll(img, 1, axis=0) - img
        nablaE = np.roll(img, -1, axis=1) - img
        nablaW = np.roll(img, 1, axis=1) - img
        if option == 1:
            cN = np.exp(-(nablaN/kappa)**2)
            cS = np.exp(-(nablaS/kappa)**2)
            cE = np.exp(-(nablaE/kappa)**2)
            cW = np.exp(-(nablaW/kappa)**2)
        else:
            cN = 1.0 / (1.0 + (nablaN/kappa)**2)
            cS = 1.0 / (1.0 + (nablaS/kappa)**2)
            cE = 1.0 / (1.0 + (nablaE/kappa)**2)
            cW = 1.0 / (1.0 + (nablaW/kappa)**2)
        img += gamma * (cN*nablaN + cS*nablaS + cE*nablaE + cW*nablaW)
    return img
