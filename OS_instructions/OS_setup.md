# Creating a fresh OS from scratch

These are instructions for creating a fresh OS image from scratch. 99% of the time, you will most likely just want to flash one of our pre-made images - see `OS_flash.md`.

## Full Installation Instructions

Install Raspbian GNU/Linux 11 (Bullseye) on a fresh 64GB SD card. Make sure to update the OS
hostname and wifi/password by pressing shift-ctrl-x. After it is flashed, pop it into a Pi and
follow the commands below.

```console
sudp apt update
sudo apt upgrade
```

## Optional but very nice things (axel would deeply appreciate it)

```console
sudo apt install tmux
cat << EOF > ~/.vimrc
set ai
set ruler
set hlsearch
set showmatch
set incsearch
set expandtab
set lazyredraw
set noswapfile
set splitbelow
set splitright
set ignorecase
set smartcase
set wildmenu
set number relativenumber

set mouse=a
set laststatus=2

set tabstop=2
set scrolloff=2
set shiftwidth=2
set softtabstop=2
set encoding=utf-8
set backspace=indent,eol,start

set signcolumn=yes:1
set fillchars+=vert:\|

set updatetime=250
set timeoutlen=300 ttimeoutlen=0

filetype plugin indent on
map <C-J> <C-W><C-J>
map <C-K> <C-W><C-K>
map <C-L> <C-W><C-L>
map <C-H> <C-W><C-H>
highlight clear SignColumn
EOF
```

### Install numba first, separately
Note: this section may become obsolete once we transition to a 64-bit OS. For now, these are the steps to get numba working on Raspbian 32-bit.

```
sudo apt install llvm-11
export LLVM_CONFIG=llvm-config-11 pip install llvmlite==0.37.0 --no-cache
pip install numba==0.56.0
```

### Install ulc-malaria-scope
```console
mkdir Documents && cd Documents
git clone https://github.com/czbiohub/ulc-malaria-scope.git
cd ulc-malaria-scope
pip3 install -e .
```

### Install cmake and some required libraries
```console
sudo apt install -y cmake
sudo apt install libusb-1.0-0-dev
sudo apt install libatlas-base-dev
pip3 install Cython>=0.29.33
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

If you are running a 64 bit OS, swap out `-DPYTHON_LIBRARY="/usr/lib/arm-linux-gnueabihf/libpython3.9.so"` with `-DPYTHON_LIBRARY="/usr/lib/aarch64-linux-gnu/libpython3.9.so"`.

### Add the openvino Python libraries to the `PYTHONPATH`

for a 32 bit OS,
```console
echo "export PYTHONPATH=/home/pi/openvino/bin/armv7l/Release/lib/python_api/python3.9:$PYTHONPATH" >> ~/.bashrc
```

and if you are running a 64 bit OS,
```console
echo "export PYTHONPATH=/home/pi/openvino/bin/aarch64/Release/lib/python_api/python3.9:$PYTHONPATH" >> ~/.bashrc
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

Download and uncompress Vimba for your version of the software:

- [Vimba 64 bit](https://drive.google.com/file/d/1_0ckwfBUPX-drv2zrvJkzIj39QkT-eUr/view?usp=share_link)
- [Vimba 32 bit](https://drive.google.com/file/d/16OUi32I5QPsywLyl9qaezAkova_Dz53e/view?usp=sharing)

`rsync` it to `/opt/`, then

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

and now reboot.

### Setting up the SSD
Instructions on Confluence here: https://czbiohub.atlassian.net/l/cp/SW5bEMJ4

Tldr:
**If choosing to format as exFAT**
1. This process is straightforward - connect the SSD to your Mac, run DiskUtility, right-click and select format, choose exFAT.
2. Rename the drive to SamsungSSD by right-clicking on it and renaming.



**For ext4, the process is a little more involved**
**Warning - formatting as ext4 means it'll be a pain to try to read the SSD on your Mac computer. The performance gains (if any) are dubious, so this section should be ignored. Likely better to just use exFAT and skip all the headache**
I outline the procedure here for MacOS, but the high-level steps are similar for Windows (it may just involve different tools)

1. Connect the SSD and use e2fsprogs to format:

  - `brew install e2fsprogs`

  - `diskutil list` (note down the name of the 4TB SSD, e.g /dev/disk2)

  - Run `sudo $(brew --prefix e2fsprogs)/sbin/mkfs.ext4 /dev/disk2`

2. Connect the SSD to a Pi / Linux system

  - Set the name of the SSD

  - Run `lsblk` and note the location of the SSD (e.g `sda` or `sda2`)

  - Run `e2label /dev/sda SamsungSSD`

3. Set the permissions of the SSD

  - `cd /media/pi/` (or wherever the SSD is located)

  - `sudo chmod 777 SamsungSSD/`

### Congrats!

You are done.
