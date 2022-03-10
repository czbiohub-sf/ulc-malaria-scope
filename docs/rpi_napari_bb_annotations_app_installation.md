``` 
python3 -m venv napari
source napari/bin/activate

# Install qt dependencies for napari
sudo apt-get install -y qt5-default pyqt5-dev pyqt5-dev-tools

# Get the bounding box annotations app
git clone https://github.com/czbiohub/napari-bb-annotations.git
cd napari-bb-annotations

# Check out to branch with tflite changes that would work for the ULC malaria parasite stage detection/annotation
git checkout pranathi-tflite

# Install tflite runtime
pip3 install https://dl.google.com/coral/python/tflite_runtime-2.1.0.post1-cp37-cp37m-linux_armv7l.whl
sudo apt-get install libcblas-dev
sudo apt-get install libhdf5-dev
sudo apt-get install libhdf5-serial-dev
sudo apt-get install libatlas-base-dev
sudo apt-get install libjasper-dev 
sudo apt-get install libqtgui4 
sudo apt-get install libqt4-test
pip3 install -r requirements_edgetpu.txt
sudo pip uninstall edgetpu
sudo apt-get remove python3-edgetpu libedgetpu1-std

# Now install the new Python library and Edge TPU runtime
sudo apt-get install python3-edgetpu libedgetpu1-std
pip3 install --upgrade pip
pip3 install --upgrade pip setuptools wheel
pip3 install git+https://github.com/napari/napari.git@3188e86950d04ad6444cf620101922ad822d9dd6
pip3 install -r requirements_pi4.txt
sudo apt-get update
python3 setup.py install 

# To make sure it is working, run the below command

python3.7 ./napari_bb_annotations/launcher/bb_annotations.py if you are installing the annotations app. 

# Run inside ipython below if you just want to test if napari install worked

ipython3 --gui=qt
from skimage import data
import napari

viewer = napari.view_image(data.astronaut(), rgb=True)
```
