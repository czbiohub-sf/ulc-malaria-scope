# import the necessary packages
from picamera.array import PiRGBArray
from picamera import PiCamera
import time
import cv2
import luminoth.predict as predict
from luminoth.tools.checkpoint import get_checkpoint_config
from luminoth.utils.predicting import PredictorNetwork

max_detections = 100
min_prob = 0.5
max_prob = 1.0
checkpoint="e1c2565b51e9"
config = get_checkpoint_config(checkpoint)
# Filter bounding boxes according to `min_prob` and `max_detections`.
if config.model.type == 'fasterrcnn':
    if config.model.network.with_rcnn:
        config.model.rcnn.proposals.total_max_detections = max_detections
    else:
        config.model.rpn.proposals.post_nms_top_n = max_detections
        config.model.rcnn.proposals.min_prob_threshold = min_prob
elif config.model.type == 'ssd':
    config.model.proposals.total_max_detections = max_detections
    config.model.proposals.min_prob_threshold = min_prob
else:
    raise ValueError(
        "Model type '{}' not supported".format(config.model.type))

# Instantiate the model indicated by the config.
network = PredictorNetwork(config)

# initialize the camera and grab a reference to the raw camera capture
camera = PiCamera()
rawCapture = PiRGBArray(camera)
# allow the camera to warmup
time.sleep(0.1)
# grab an image from the camera
camera.capture(rawCapture, format="bgr")
image = rawCapture.array
print(image.shape)
objects = predict.run_image_through_network(network, image, save_path="predicted_image.png")
predicted_image = cv2.imread("predicted_image.png")
# display the image on screen and wait for a keypress
cv2.imshow("Image", predicted_image)
cv2.waitKey(0)
