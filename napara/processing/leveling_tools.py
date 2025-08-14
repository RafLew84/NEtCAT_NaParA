import numpy as np

def subtract_poly_level(img, degree=1):
    X, Y = np.meshgrid(np.arange(img.shape[1]), np.arange(img.shape[0]))
    Z = img
    G = np.column_stack([X.ravel()**i * Y.ravel()**j
                         for i in range(degree+1)
                         for j in range(degree+1-i)])
    m, _, _, _ = np.linalg.lstsq(G, Z.ravel(), rcond=None)
    trend = np.dot(G, m).reshape(img.shape)
    return img - trend
