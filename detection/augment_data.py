import imgaug as ia
from imgaug import augmenters as iaa
import pandas as pd
import os
import glob
import natsort
import sys
import skimage.io

dicts = []

output_random_df = pd.read_csv(sys.argv[1])
path = sys.argv[2]
image_paths = natsort.natsorted(
    glob.glob(os.path.join(path, "*.jpg")))

sometimes = lambda aug: iaa.Sometimes(0.5, aug)
seq = iaa.Sequential([
    iaa.Flipud(1.0),  # vertically flips
    iaa.Fliplr(1.0),  # horizontal flips
    # Add gaussian noise.
    # For 50% of all images, we sample the noise once per pixel.
    # For the other 50% of all images, we sample the noise per pixel AND
    # channel. This can change the color (not only brightness) of the
    # pixels.
    # But we only blur about 50% of all images.
    iaa.Sometimes(
        0.5,
        iaa.GaussianBlur(sigma=(0, 0.5))),
    sometimes(iaa.Affine(
        scale={"x": (0.8, 1.2), "y": (0.8, 1.2)}, # scale images to 80-120% of their size, individually per axis
        translate_percent={"x": (-0.2, 0.2), "y": (-0.2, 0.2)}, # translate by -20 to +20 percent (per axis)
        rotate=(-45, 45), # rotate by -45 to +45 degrees
        shear=(-16, 16), # shear by -16 to +16 degrees
        order=[0, 1], # use nearest neighbour or bilinear interpolation (fast)
        cval=(0, 255), # if mode is constant, use a cval between 0 and 255
        mode=ia.ALL # use any of scikit-image's warping modes (see 2nd image from the top for examples)
    )),
    iaa.Sharpen(alpha=(0, 1.0), lightness=(0.75, 1.5)), # sharpen images
    iaa.Emboss(alpha=(0, 1.0), strength=(0, 2.0)), # emboss images
    # search either for all edges or for directed edges,
    # blend the result with the original image using a blobby mask
    iaa.SimplexNoiseAlpha(iaa.OneOf([
        iaa.EdgeDetect(alpha=(0.5, 1.0)),
        iaa.DirectedEdgeDetect(alpha=(0.5, 1.0), direction=(0.0, 1.0)),
    ])),
    iaa.AdditiveGaussianNoise(loc=0, scale=(0.0, 0.05*255), per_channel=0.5), # add gaussian noise to images
    iaa.OneOf([
        iaa.Dropout((0.01, 0.1), per_channel=0.5), # randomly remove up to 10% of the pixels
        iaa.CoarseDropout((0.03, 0.15), size_percent=(0.02, 0.05), per_channel=0.2),
    ]),
    iaa.Invert(0.05, per_channel=True), # invert color channels
    iaa.Add((-10, 10), per_channel=0.5), # change brightness of images (by -10 to 10 of original value)
    iaa.AddToHueAndSaturation((-20, 20)), # change hue and saturation
    # either change the brightness of the whole image (sometimes
    # per channel) or change the brightness of subareas
    iaa.OneOf([
        iaa.Multiply((0.5, 1.5), per_channel=0.5),
        iaa.FrequencyNoiseAlpha(
            exponent=(-4, 0),
            first=iaa.Multiply((0.5, 1.5), per_channel=True),
            second=iaa.LinearContrast((0.5, 2.0))
        )
    ]),
    iaa.LinearContrast((0.5, 2.0), per_channel=0.5), # improve or worsen the contrast
    iaa.AdditiveGaussianNoise(
        loc=0, scale=(0.0, 0.05 * 255), per_channel=0.5)], random_order=True)
# Make some images brighter and some darker.
# In 20% of all cases, we sample the multiplier once per channel,
# which can end up changing the color of the images.
# iaa.Multiply((0.8, 1.2), per_channel=0.2)], random_order=True)

for image_path in image_paths:
    image = skimage.io.imread(image_path)
    tmp_df = output_random_df[output_random_df.filename == image_path]

    bbs_per_image = []
    labels_per_image = []
    for index, row in tmp_df.iterrows():
        bbs_per_image.append(
            ia.BoundingBox(
                x1=row.xmin, y1=row.ymin,
                x2=row.xmax, y2=row.ymax,
                label=row.label))
    print(image.shape)
    images_aug, bbs_aug = seq(images=[image], bounding_boxes=bbs_per_image)
    print(len(images_aug))
    print(images_aug[0].shape)
    for index, bbs_per_image in enumerate(bbs_aug):
        aug_path = image_path.replace(
            ".jpg", "aug_{}.jpg".format(index))
        print(aug_path)
        skimage.io.imsave(aug_path, images_aug[index])
        for bb in bbs_per_image:
            dicts.append(
                {
                    'filename': aug_path,
                    'xmin': bb.x1,
                    'xmax': bb.x2,
                    'ymin': bb.y1,
                    'ymax': bb.y2,
                    'label': bb.label})

for d in dicts:
    output_random_df = output_random_df.append(
        d, ignore_index=True)

output_random_df.to_csv("output_random_df_aug.csv")
