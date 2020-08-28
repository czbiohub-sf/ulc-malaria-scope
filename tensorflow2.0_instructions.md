Below creates a virutal environment with pillow, numpy, opencv, and tensorflow 2.0 
```pip3 install virtualenv
python3 -m virtualenv -p $(which python3) venv_lite
source venv_lite/bin/activate
pip3 install Pillow numpy
wget https://github.com/PINTO0309/Tensorflow-bin/raw/master/tensorflow-2.1.0-cp37-cp37m-linux_armv7l.whl
pip3 install --upgrade setuptools
pip3 install tensorflow-*-linux_armv7l.whl
````
Get the coco model to test on 

```wget https://storage.googleapis.com/download.tensorflow.org/models/tflite/coco_ssd_mobilenet_v1_1.0_quant_2018_06_29.zip
unzip coco_ssd_mobilenet_v1_1.0_quant_2018_06_29.zip -d Sample_TFLite_model

```
For the COCO dataset I used, I dowloaded data as below and made a video using ffmpeg from the images, and raspberry pi camera is pointed at the video

```
wget http://images.cocodataset.org/zips/val2017.zip
unzip val2017.zip -d val2017
cd val2017
ffmpeg -pattern_type glob -i '*.jpg' -vf "setpts=5*PTS" test_r5.mp4
```
Then clone a repo that contains the tensorflow lite based prediction on images
```
git clone https://github.com/EdjeElectronics/TensorFlow-Lite-Object-Detection-on-Android-and-Raspberry-Pi.git
```
Run the real time object detection pointing raspberry pi camera towards objects commonly found in COCO and COCO model downloaded
```
python3 TFLite_detection_webcam.py --modeldir=Sample_TFLite_model
```
