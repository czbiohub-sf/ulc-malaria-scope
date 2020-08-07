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
# initialize the camera and grab a reference to the raw camera capture
camera = PiCamera()
camera.resolution = (696, 512)
camera.framerate = 5
rawCapture = PiRGBArray(camera, size=(696, 512))
# allow the camera to warmup
time.sleep(0.1)
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
index = 0
# capture frames from the camera
for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
    # grab the raw NumPy array representing the image, then initialize the timestamp
    # and occupied/unoccupied text
    image = frame.array
    image = cv2.resize(image, (696,512))
    print(image.shape)
    objects = predict.run_image_through_network(network, image, save_path="predicted_image_{}.jpg".format(index))
    print(objects)
    # show the frame
    predicted_image = cv2.imread("predicted_image_{}.jpg".format(index))
    cv2.imshow("Frame", predicted_image)
    cv2.imwrite("image_{}.jpg".format(index), image)
    index += 1
    key = cv2.waitKey(1) & 0xFF
    # clear the stream in preparation for the next frame
    rawCapture.truncate(0)
    # if the `q` key was pressed, break from the loop
    if key == ord("q"):
        break
