from numba import njit
import numpy as np
import cv2


def downsample_image(img: np.ndarray, scale_factor: int) -> np.ndarray:
    """Downsamples an image by `scale_factor`"""
    h, w = img.shape
    return cv2.resize(img, (w // scale_factor, h // scale_factor))


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


def gradientAverage(img: np.ndarray):
    """Returns the normalized (by mean) gradient average (in x and y)"""
    gx, gy = np.gradient(img) / np.mean(img)
    return np.average(np.sqrt(gx**2 + gy**2))


def varianceOfLaplacian(img):
    return cv2.Laplacian(img, cv2.CV_64F).var()


@njit(cache=True)
def get_diff(img: np.ndarray):
    img = np.asarray(img, dtype=np.float32)
    gx = np.zeros_like(img)
    gy = np.zeros_like(img)
    rows, cols = img.shape

    # Top left edge
    gx[0, 0] = img[0, 1] - img[0, 0]
    gy[0, 0] = img[1, 0] - img[0, 0]

    # Top right edge
    gx[0, -1] = img[0, -1] - img[0, -2]
    gy[0, -1] = img[1, -1] - img[0, -1]

    # Bottom left edge
    gx[-1, 0] = img[-1, 1] - img[-1, 0]
    gy[-1, 0] = img[-1, 0] - img[-2, 0]

    # Bottom right edge
    gx[-1, -1] = img[-1, -1] - img[-1, -2]
    gy[-1, -1] = img[-1, -1] - img[-2, -1]

    # Top/bottom row
    for i in range(1, cols - 1):
        gx[0, i] = (img[0, i + 1] - img[0, i - 1]) / 2
        gy[0, i] = img[1, i] - img[0, i]

        gx[-1, i] = (img[-1, i + 1] - img[-1, i - 1]) / 2
        gy[-1, i] = img[-1, i] - img[-2, i]

    # First/last columns
    for j in range(1, rows - 1):
        gx[j, 0] = img[j, 1] - img[j, 0]
        gy[j, 0] = (img[j + 1, 0] - img[j - 1, 0]) / 2

        gx[j, -1] = img[j, -1] - img[j, -2]
        gy[j, -1] = (img[j + 1, -1] - img[j - 1, -1]) / 2

    # Inner
    for i in range(1, rows - 1):
        for j in range(1, cols - 1):
            gx[i, j] = (img[i, j + 1] - img[i, j - 1]) / 2
            gy[i, j] = (img[i + 1, j] - img[i - 1, j]) / 2

    return gy, gx


def numba_mean(img: np.ndarray):
    return np.mean(img)


@njit(cache=True)
def custom_gradient_average(img: np.ndarray):
    # I know these are flipped from what the return statement in `get_diff`
    # but my 'gy' corresponds to np.gradient's 'gx'
    # and rewriting `get_diff` is a bit of a pain and ultimately inconsequential
    # for how we're using it here
    img_mean = np.mean(img)
    gx, gy = get_diff(img)
    gx = gx / img_mean
    gy = gy / img_mean

    return np.mean(np.sqrt(gx**2 + gy**2))
