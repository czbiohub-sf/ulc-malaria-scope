import sys

import cv2
import pandas as pd

import imgaug as ia

width = 4256
height = 2832
input_args = sys.argv

for csv_path in input_args[1:]:

    df = pd.read_csv(csv_path, index_col=0)
    first = True

    cnt = 0
    error_cnt = 0
    error = False
    for index, row in df.iterrows():

        bb = ia.BoundingBox(x1=row.xmin, y1=row.ymin,
                            x2=row.xmax, y2=row.ymax,
                            label=row.label)
        img = cv2.imread(row.filename)
        if img is None:
            print(row.filename)

        if not bb.compute_out_of_image_fraction(img) <= 0.2:
            df = df.drop([index])
        if error:
            error_cnt += 1
            error = False

        if first:
            first = False
            continue

        cnt += 1
        org_height, org_width = img.shape[:2]
        name = row.filename
        xmin = row.xmin
        xmax = row.xmax
        ymin = row.ymin
        ymax = row.ymax
        label = row.label

        if org_width != width:
            error = True
            print('Width mismatch for image: ', name, width, '!=', org_width)

        if org_height != height:
            error = True
            print(
                'Height mismatch for image: ', name, height, '!=', org_height)
        if xmin > org_width:
            error = True
            xmin = org_width
            print('XMIN {} > org_width for file {}'.format(xmin, name))

        if xmin < 0:
            error = True
            xmin = 0
            print('XMIN {} < 0 for file {}'.format(xmin, name))

        if xmax > org_width:
            error = True
            xmax = org_width
            print('XMAX {} > orig_width {} for file {}'.format(xmax, org_width, name))

        if ymin > org_height:
            error = True
            ymin = org_height
            print('YMIN {} > org_height {} for file {}'.format(ymin, org_height, name))

        if ymin < 0:
            error = True
            ymin = 0
            print('YMIN {} < 0 for file {}'.format(ymin, name))
        df.loc[index] = name, xmin, xmax, ymin, ymax, label
        if ymax > org_height:
            error = True
            ymax = org_height
            print('YMAX {} > org_height {} for file {}'.format(ymax, org_height, name))

        if xmin >= xmax:
            error = True
            print('xmin {} >= xmax {} for file {} '.format(xmin, xmax, name))
        if ymin >= ymax:
            error = True
            print('ymin {} >= ymax {} for file {}'.format(ymin, ymax, name))
        if error:
            print('Error for file: %s' % name)
            print()
    print('Checked %d files and realized %d errors' % (cnt, error_cnt))
    df.to_csv(csv_path, index=False)
