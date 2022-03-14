import numpy as np
import cv2

def logPowerSpectrumRadialAverageSum(img):
    def radial_average(arr):
        w, h = arr.shape[1], arr.shape[0]
        cx, cy = w // 2, h // 2

        # Create centered radius matrix
        x, y = np.meshgrid(np.arange(w) - cx, np.arange(h) - cy)
        R = np.sqrt(x**2 + y**2)

        # Compute radial mean 
        rm = lambda r: arr[(R >= r - 0.5) & (R <= r + 0.5)].mean()
        r = np.linspace(1, int(np.max(R)))
        radial_mean = np.vectorize(rm)(r)
        return radial_mean

    power_spectrum = np.fft.fftshift(np.fft.fft2(img))
    log_ps = np.log(np.abs(power_spectrum))
    return np.sum(radial_average(log_ps))

def gradientAverage(img):
    gx, gy = np.gradient(img)
    return np.average(np.sqrt(gx**2 + gy**2))

def varianceOfLaplacian(img):
    return cv2.Laplacian(img, cv2.CV_64F).var()

if __name__ == "__main__":
    import sys
    import os
    import inspect
    import matplotlib.pyplot as plt

    funcs = [obj for _, obj in inspect.getmembers(sys.modules[__name__]) if (inspect.isfunction(obj))]
    metrics = [[] for _ in range(len(funcs))]
    imgs = [cv2.imread("test_images/2022-03-11-145013-zstack/"+img, 0) for img in sorted(os.listdir("test_images/2022-03-11-145013-zstack")) if '.jpg' in img]
    
    for i, func in enumerate(funcs):
        for img in imgs:
            metrics[i].append(func(img))
    for i, metric in enumerate(metrics):
        plt.figure()
        plt.plot(range(0, 900, 10), metric, 'o', markersize=2, color='#2CBDFE')
        plt.title(f"{funcs[i].__name__}")
        plt.xlabel("Motor position (um)")
        plt.ylabel("Focus metric")
    plt.show()