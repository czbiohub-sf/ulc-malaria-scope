import numpy as np
import cv2


def logPowerSpectrumRadialAverageSum(img):
    def radial_average(data):
        data = data / np.max(data)
        h, w = data.shape[0], data.shape[1]
        center = (w // 2, h // 2)
        y, x = np.indices((data.shape))
        r = np.sqrt((x - center[0]) ** 2 + (y - center[1]) ** 2)
        r = r.astype(int)

        tbin = np.bincount(r.ravel(), data.ravel())
        nr = np.bincount(r.ravel())
        radialprofile = tbin / nr
        return radialprofile

    power_spectrum = np.fft.fftshift(np.fft.fft2(img))
    log_ps = np.log(np.abs(power_spectrum))
    return np.sum(radial_average(log_ps))


def gradientAverage(img):
    """Returns the normalized gradient average (in x and y)"""
    gx, gy = np.gradient(img) / np.max(img)
    return np.average(np.sqrt(gx**2 + gy**2))


def varianceOfLaplacian(img):
    return cv2.Laplacian(img, cv2.CV_64F).var()
