import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from skimage.filters import threshold_otsu
import skimage.measure

import pims
import trackpy as tp

# Optionally, tweak styles.
mpl.rc('figure', figsize=(10, 5))
mpl.rc('image', cmap='gray')


@pims.pipeline
def scale_to_uint8(image):
    return ((image - image.min()) / (image.max() - image.min()) * 255).astype(np.uint8)

path = "/Users/pranathi.vemuri/Downloads/example_data/"
frames = scale_to_uint8(pims.open(path + '*.tif'))
df = pd.DataFrame(columns=['y', 'x', 'frame'])
centroids = []
count = 0
for frame in frames:
    thresholded_image = np.zeros(
        (frame.shape[0], frame.shape[1]), dtype=np.uint8)
    thresh_value = threshold_otsu(frame)
    thresholded_image[frame < thresh_value] = 255
    label_image = skimage.measure.label(thresholded_image)
    for region in skimage.measure.regionprops(label_image):
        # take regions with large enough areas
        if region.area >= 1000 and region.area <= 5000:
            ymin, xmin, ymax, xmax = region.bbox
            centroid = tuple(((xmin + xmax) // 2, (ymin + ymax) // 2))
            centroids.append(centroid)
            df = df.append(
                {"y": centroid[1], "x": centroid[0], "frame": count},
                ignore_index=True)
    count += 1
t = tp.link(df, 50, memory=3)
tp.annotate(t[t['frame'] == 0], frames[0])
plt.figure()
tp.plot_traj(t);
