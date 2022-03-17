Install the below either in venv or miniconda enviroment 
(I found the miniconda installation had conflicting python3 and pip paths and was not actually
working-everything was installed outside of the conda environment but they worked).

```
python3 -m venv tutorial-env
```

or 

```bash
wget https://repo.anaconda.com/miniconda/Miniconda-3.16.0-Linux-armv7l.sh
bash Miniconda-3.16.0-Linux-armv7l.sh
source ~/.bashrc
```

To install pip

```bash
sudo apt install python3-pip
```

To install necessary apt dependencies

```bash
sudo apt-get install build-essential cmake pkg-config
sudo apt-get install libgdk-pixbuf2.0-dev libpango1.0-dev
sudo apt-get install libgtk2.0-dev libgtk-3-dev
sudo apt-get install libatlas-base-dev gfortran
sudo apt-get install libhdf5-dev libhdf5-serial-dev libhdf5-103
sudo apt-get install libqtgui4 libqtwebkit4 libqt4-test python3-pyqt5
sudo apt-get install libatlas-base-dev
sudo apt-get install libjasper-dev
sudo apt-get install libqtgui4
sudo apt-get install python3-pyqt5
```

To install dependencies of this repo and to run the commands with prediction
```bash
git clone https://github.com/czbiohub/ulc-malaria-scope.git
pip install -r requirements_lumi_pi4.txt
git clone https://github.com/czbiohub/luminoth-uv-imaging.git
cd luminoth
pip install -e .
```

## Check that the installation worked

Simply run `lumi --help`.

# For more info on lumi go to 
https://github.com/czbiohub/luminoth-uv-imaging/blob/master/README.md
