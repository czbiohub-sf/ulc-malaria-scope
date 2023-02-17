# Creating a fresh OS from scratch

These are instructions for creating a fresh OS image from scratch. 99% of the time, you will most likely just want to flash one of our pre-made images - see `OS_fash.md`.

## Full Installation Instructions

Install Raspbian GNU/Linux 11 (bullseye) on a fresh 64GB SD card. Make sure to update the OS
hostname and wifi/password by pressing shift-ctrl-x. After it is flashed, pop it into a Pi and
follow the commands below.

```console
sudp apt update
sudo apt upgrade
```

### Install ulc-malaria-scope
```console
mkdir Documents && cd Documents
git clone https://github.com/czbiohub/ulc-malaria-scope.git
cd ulc-malaria-scope
pip3 install -e .
```

### Install cmake and some req'd libraries
```console
sudo apt install -y cmake
sudo apt install libusb-1.0-0-dev
sudo apt install libatlas-base-dev
```

### Install Openvino

Please note: I found that a *lot* of the documentation for the installation of Openvino is simply wrong. I suspect that it is way out of date, and nobody at Intel bother to update it. The instructions I have below are the result of what I found to work, but it could change in future Openvino versions. A *large* part of figuring it out was looking at the post-install setup scripts that openvino wrote (primarily setupvars.sh and install_NCS_udev_rules.sh), figuring out what those scripts were *supposed* to do, and doing those steps. At the very least, you learn a lot about linux when installing all of this ;)

```console
cd ~
git clone https://github.com/openvinotoolkit/openvino.git
cd openvino
git checkout tags/2022.1.1
git submodule update --init --recursive
mkdir build && cd build

# Takes a long time! Maybe ~4 hrs?
cmake \
  -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_PYTHON=ON \
  -DPYTHON_EXECUTABLE="/usr/bin/python3"  \
  -DPYTHON_LIBRARY="/usr/lib/arm-linux-gnueabihf/libpython3.9.so"  \
  -DPYTHON_INCLUDE_DIR="/usr/include/python3.9"  \
  -DCYTHON_EXECUTABLE="/home/pi/.local/bin/cython"  \
  -DENABLE_OV_TF_FRONTEND_ENABLE=OFF  \
  -DENABLE_OV_PDPD_FRONTEND_ENABLE=OFF  \
  -DENABLE_SAMPLES=OFF  \
  -DENABLE_HETERO=OFF  \
  .. && make --jobs=$(nproc --all)
```

### Add the openvino Python libraries to the `PYTHONPATH`
```console
export PYTHONPATH=/home/pi/openvino/bin/armv7l/Release/lib/python_api/python3.9:$PYTHONPATH
```

### Manually update NCS2 udev rules

```console
# add yourself to group
sudo usermod -a -G users "$(whoami)"

# Now find the file "97-myriad-usbboot.rules" - for me, it was at
#   /home/pi/openvino/src/plugins/intel_myriad/third_party/mvnc/src/97-myriad-usbboot.rules
# If yours is in a different place, replace my path with yours below

sudo cp /home/pi/openvino/src/plugins/intel_myriad/third_party/mvnc/src/97-myriad-usbboot.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo ldconfig
```

### Install Vimba

I could not find Vimba for `armv71` online. I `rsync`'d the source (Vimba for Linux ARMv7 32-bit - Release Notes) from a previous Malaria Scope's OS and installed
from there.

I `rsync`'d it to `/opt/`, then
```console
cd /opt/Vimba_5_0/VimbaUSBTL
sudo ./Install.sh
sudo reboot
```

after reboot,

```console
cd /opt/Vimba_5_0/VimbaPython
sudo ./Install.sh
```

### Updating boot/config.txt
Now is a good time to take a breath. You've made it through the worst of it!
Add the following to `/boot/config.txt` (at the bottom, under `[all]` if it is there)

```console
start_x=1
dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
gpu_mem=128
```

Uncomment the following

```console
dtparam=i2c_arm=on
```

and now reboot.


### Install Others

To automate running the daemon at boot time, run:

```console
sudo systemctl enable pigpiod
```

### Instantiate our ulc-malaria-scope services

```console
sudo cp ~/Documents/ulc-malaria-scope/ulc_mm_package/utilities/systemd_init_scripts/init_led_pneumatic.service /lib/systemd/system
sudo chmod 644 /lib/systemd/system/init_led_pneumatic.service

sudo cp ~/Documents/ulc-malaria-scope/ulc_mm_package/utilities/systemd_init_scripts/fan.service /lib/systemd/system
sudo chmod 644 /lib/systemd/system/fan.service

sudo systemctl daemon-reload
sudo systemctl enable init_led_pneumatic.service
sudo systemctl enable fan.service
```

### Congrats!

You are done!
