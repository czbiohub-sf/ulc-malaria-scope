Below creates a virutal environment with pillow, numpy, and tensorflow lite runtime libraries, edgetpu library dependencies
```pip3 install virtualenv
python3 -m virtualenv -p $(which python3) venv_tflite_edgetpu
source venv_tflite_edgetpu/bin/activate
pip3 install Pillow numpy
pip3 uninstall tensorflow
pip3 install https://dl.google.com/coral/python/tflite_runtime-2.1.0.post1-cp37-cp37m-linux_armv7l.whl
pip3 install --upgrade setuptools
echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo apt-get update
sudo apt-get install libedgetpu1-max
````
Get the coco edgetpu model to test on 

```
mkdir Sample_TFLite_model
wget https://dl.google.com/coral/canned_models/mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite
mv mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite Sample_TFLite_model/edgetpu.tflite

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
python3 TFLite_detection_webcam.py --modeldir=Sample_TFLite_model --edgetpu
```
