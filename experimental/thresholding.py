import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from skimage.io import imread
from skimage.measure import label, regionprops
from skimage.color import label2rgb
from scipy import ndimage as ndi

from skimage.segmentation import watershed
from skimage.feature import peak_local_max


path = "/Users/pranathi.vemuri/Downloads/8aprilimgs/8april-frame00001.jpg"
numpy_image = imread(path)[:, :, 0]
thresholded_image = np.zeros(
    (numpy_image.shape[0], numpy_image.shape[1]), dtype=np.uint8
)
thresh_value = 128
thresholded_image[numpy_image < thresh_value] = 255
distance = ndi.distance_transform_edt(thresholded_image)
coords = peak_local_max(distance, footprint=np.ones((3, 3)), labels=thresholded_image)
mask = np.zeros(distance.shape, dtype=bool)
mask[tuple(coords.T)] = True
markers, _ = ndi.label(mask)
labels = watershed(-distance, markers, mask=thresholded_image)
fig, axes = plt.subplots(ncols=3, figsize=(9, 3), sharex=True, sharey=True)
ax = axes.ravel()

ax[0].imshow(thresholded_image, cmap=plt.cm.gray)
ax[0].set_title("Overlapping objects")
ax[1].imshow(-distance, cmap=plt.cm.gray)
ax[1].set_title("Distances")
ax[2].imshow(labels)
ax[2].set_title("Separated objects")

for a in ax:
    a.set_axis_off()

fig.tight_layout()
plt.show()


# apply threshold

# remove artifacts connected to image border
# cleared = clear_border(thresholded_image)

# label image regions
label_image = label(thresholded_image)
# to make the background transparent, pass the value of `bg_label`,
# and leave `bg_color` as `None` and `kind` as `overlay`
image_label_overlay = label2rgb(label_image, image=numpy_image, bg_label=0)

fig, ax = plt.subplots(figsize=(10, 6))
ax.imshow(numpy_image, cmap="gray")

for region in regionprops(label_image):
    # take regions with large enough areas
    if region.area >= 500:
        # draw rectangle around segmented coins
        minr, minc, maxr, maxc = region.bbox
        rect = mpatches.Rectangle(
            (minc, minr),
            maxc - minc,
            maxr - minr,
            fill=False,
            edgecolor="red",
            linewidth=2,
        )
        ax.add_patch(rect)

ax.set_axis_off()
plt.tight_layout()
plt.show()
