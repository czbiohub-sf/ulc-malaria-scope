#!/bin/bash

echo "Installing dependencies..."
sudo apt-get build-dep -y  qt5-default

sudo apt-get install -y '^libxcb.*-dev' libx11-xcb-dev libglu1-mesa-dev libxrender-dev libxi-dev libxkbcommon-dev libxkbcommon-x11-dev

sudo apt-get install -y flex bison gperf libicu-dev libxslt-dev ruby nodejs

sudo apt-get install -y libxcursor-dev libxcomposite-dev libxdamage-dev libxrandr-dev libxtst-dev libxss-dev libdbus-1-dev libevent-dev libfontconfig1-dev libcap-dev libpulse-dev libudev-dev libpci-dev libnss3-dev libasound2-dev libegl1-mesa-dev

sudo apt-get install -y libasound2-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libgstreamer-plugins-bad1.0-dev

sudo apt-get install -y freeglut3-dev

sudo apt install -y libclang-6.0-dev llvm-6.0

echo "Getting Qt from source and building...this will take a long time (6+ hours). See ya later cowboy..."
wget https://raw.githubusercontent.com/tiagordc/raspberry-pi-qt-builds/master/build-qt.sh

sudo chmod +x build-qt.sh

sh build-qt.sh

echo "Done building. Starting install..."
cd / 

sudo tar xf /home/pi/qtbuild/Qt5.15.2-rpi-bin-minimal.tgz

text1 = "export LD_LIBRARY_PATH=/usr/local/Qt-5.15.2/lib:$LD_LIBRARY_PATH"
text2 = "export PATH=/usr/local/Qt-5.15.2/bin:$PATH"
echo $text1 >> ~/.bashrc
echo $text2 >> ~/.bashrc

echo "Building PyQt5...this will take a long time (3+ hours). See ya later cowgirl..."

sudo apt-get install sip-dev

cd /usr/src

sudo wget https://www.riverbankcomputing.com/static/Downloads/sip/4.19.24/sip-4.19.24.tar.gz

sudo wget https://files.pythonhosted.org/packages/28/6c/640e3f5c734c296a7193079a86842a789edb7988dca39eab44579088a1d1/PyQt5-5.15.2.tar.gz

sudo tar xzf sip-4.19.24.tar.gz

sudo tar xzf PyQt5-5.15.2.tar.gz

cd sip-4.19.24

sudo python3 configure.py --sip-module PyQt5.sip

sudo make -j4

sudo make install

cd ../PyQt5-5.15.2

sudo python3 configure.py --qmake /usr/local/Qt-5.15.2/bin/qmake --confirm-license

sudo make -j4

sudo make install

sudo wget https://raw.githubusercontent.com/tiagordc/rpi-build-qt-pyqt/master/test.py
python3 test.py

echo "And that's a wrap!"
