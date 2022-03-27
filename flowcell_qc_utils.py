import cv2
import numpy as np

path = "/Users/pranathi.vemuri/Documents/image-20220131-171504.png"
template_path = "/Users/pranathi.vemuri/Documents/template.png"

img = cv2.imread(path, cv2.IMREAD_COLOR)
# Convert the image to gray-scale
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
# Find the edges in the image using canny detector
edges = cv2.Canny(gray, 50, 200)
max_slider = 0
# Detect points that form a line
lines = cv2.HoughLinesP(
    edges, 1, np.pi / 180, max_slider, minLineLength=10, maxLineGap=250
)
# Draw lines on the image
for line in lines:
    x1, y1, x2, y2 = line[0]
    cv2.line(img, (x1, y1), (x2, y2), (255, 0, 0), 3)
# Show result
cv2.imshow("Result Image", img)

img_rgb = cv2.imread(path)
img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)
template = cv2.imread(template_path, 0)
w, h = template.shape[::-1]
res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
for threshold in range(1, 10):
    img_rgb = cv2.imread(path)
    threshold = 0.1 * threshold
    loc = np.where(res >= threshold)
    for pt in zip(*loc[::-1]):
        cv2.rectangle(img_rgb, pt, (pt[0] + w, pt[1] + h), (0, 0, 255), 2)
    cv2.imwrite("res_{}.png".format(threshold), img_rgb)
