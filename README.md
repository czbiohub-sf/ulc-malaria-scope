# Ultra-Low Cost (ULC) malaria scope

Welcome to the ULC Malaria Scope! We are developing a barebones optical microscope with embedded computing hardware capable of dianosing malaria in fresh, whole blood with no fixation, staining, or preparation steps. No highly trained technicians will be required to perform time-consuming sample preparation or manual scoring of parasites under the microscope. The target BOM cost is $250.

## Introduction

## Optics

## Realtime malaria detection

## Hardware

## Flow cell

### Flexure-based autofocus

## Software operation

### Installing dependencies
In the root folder, run <code>pip install -e .</code> to install all pip dependencies. There are also some modules that need to be manually installed:

Allied Vision's Vimba library:
# Check that Python 3.7 is installed and verify with <code>python --version</code>
# Check that pip is up to date and verify with <code>python -m pip --version</code>
# [Download the SDK](https://www.alliedvision.com/en/products/vimba-sdk/#c1497).
# Navigate to the "VimbaPython" installation directory in a terminal and run <code>python -m pip install .</code>

Openvino library (only if runnning on your own machine, instead of a Raspberry Pi):
# Python version should be 3.9 or lower
# Run <code>pip install openvino</code>

### Starting the GUI
Navigate to ulc_mm_package/QtQUI and run <code>python3 UI.py</code>. Use optional flags to enable operation modes:
* <code>-s</code> or <code>--sim</code>: Simulation mode (dummy functions replace hardware objects)
* <code>-d</code> or <code>--dev</code>: Developer mode (manual control of hardware objects)

Note: The original GUI was activated by liveviewer.py, which is now obsolete. Use UI.py instead.
