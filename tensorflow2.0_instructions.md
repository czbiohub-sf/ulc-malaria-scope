```pip3 install virtualenv
pthon3 -m virtualenv -p $(which python3) venv_lite
source venv_lite/bin/activate
pip3 install Pillow numpy pygame
wget https://github.com/PINTO0309/Tensorflow-bin/raw/master/tensorflow-2.1.0-cp37-cp37m-linux_armv7l.whl
pip3 install --upgrade setuptools
pip3 install tensorflow-*-linux_armv7l.whl
git clone --depth 1 https://github.com/adafruit/rpi-vision.git
cd rpi-vision
pip3 install -e .```
