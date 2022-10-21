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

### Running the GUI

Navigate to ulc_mm_package/QtGUI and run `python3 oracle.py`.

Note: The original GUI lived in `liveviewer.py`, which is now obsolete. Use the above command instead.

### Debugging using developer mode

Navigate to ulc_mm_package/QtGUI and run `python3 dev_run.py`. This opens a GUI with manual hardware control for debugging purposes.

### Using simulation mode

To run any of these scripts using simulated hardware (eg. to test code without a scope), set `MS_SIMULATE=1` (either for the single command, like `MS_SIMULATE=1 python3 oracle.py`, or until you restart your shell, like `export MS_SIMULATE=1`

You will also need to have a video saved locally, which will replace the camera input. By default, the video should be saved under ulc_mm_package/QtGUI/sim_media/sample.avi, but you can change the filename and location by editing the constant `VIDEO_PATH` under ulc_mm_package/hardware/hardware_constants.py. It can be an `avi` or `mp4` file.
