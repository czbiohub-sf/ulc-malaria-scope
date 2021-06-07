``` 
python3 -m venv napari
source napari/bin/activate
sudo apt-get install -y qt5-default pyqt5-dev pyqt5-dev-tools
git clone https://github.com/czbiohub/napari-bb-annotations.git
cd napari-bb-annotations
git checkout pranathi-tflite
pip3 install --upgrade pip
pip3 install git+git://github.com/napari/napari.git@3188e86950d04ad6444cf620101922ad822d9dd6
pip3 install -r requirements_pi4.txt
sudo apt-get update
python3 setup.py install 
```
