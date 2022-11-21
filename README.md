# Ultra-Low Cost (ULC) malaria scope

Welcome to the ULC Malaria Scope! We are developing a barebones optical microscope with embedded computing hardware capable of dianosing malaria in fresh, whole blood with no fixation, staining, or preparation steps. No highly trained technicians will be required to perform time-consuming sample preparation or manual scoring of parasites under the microscope. The target BOM cost is $250.

## Introduction

## Optics

## Realtime malaria detection

## Hardware

## Flow cell

### Flexure-based autofocus

## Software operation

### Development

Before commiting, make sure to run

`black .`

in the root of this project. This will autoformat your files for you.

### Installing dependencies

In the root folder, run `pip install -e .` to install all pip dependencies.

To develop, run `pip install -e .[dev]`

### Running the GUI

Navigate to ulc_mm_package/QtGUI and run `python3 oracle.py`.

Note: The original GUI lived in `liveviewer.py`, which is now obsolete. Use the above command instead.

### Debugging using developer mode

Navigate to ulc_mm_package/QtGUI and run `python3 dev_run.py`. This opens a GUI with manual hardware control for debugging purposes.

### Using simulation mode

To run any of these scripts using simulated hardware (eg. to test code without a scope), set `MS_SIMULATE=1` (either for the single command, like `MS_SIMULATE=1 python3 oracle.py`, or until you restart your shell, like `export MS_SIMULATE=1`

You will also need to have a video saved locally, which will replace the camera input. By default, the video should be saved under ulc_mm_package/QtGUI/sim_media/sample.avi, but you can change the filename and location by editing the constant `VIDEO_PATH` under ulc_mm_package/hardware/hardware_constants.py. It can be an `avi` or `mp4` file.

#### SSH Development

You can do the required development on the Pi through SSH. You have two options.

The first is rendering "offscreen". This can be done by setting the environment variable `QT_QPA_PLATFORM=offscreen`.

The next thing is X11 forwarding. On Mac, you have to setup [XQuartz](https://www.xquartz.org/), and you will probably have to do something different on different platforms. To use X11 forwarding, `ssh` into your pi with the `-Y` option (safe X11 forwarding). You should then be able to run any command with a GUI, and one should pop up on screen.

#### Remote SSH using `ngrok`
1. Set up `ngrok` on a new device by:

```
wget https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-arm.zip
unzip ngrok-stable-linux-arm.zip
ngrok authtoken {TOKEN HERE}
```

2. `cd` to the directory where `ngrok` is downloaded.

3. Run `ngrok` with:
```
./ngrok tcp 22
```
